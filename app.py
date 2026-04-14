"""
ResumeForge AI — Web Application
Flask backend: handles resume upload, job link processing, real-time SSE
progress streaming, and PDF download delivery.
"""
from __future__ import annotations

import json
import os
import queue
import threading
import traceback
import uuid
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template, request, send_file
from werkzeug.utils import secure_filename

load_dotenv(override=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024   # 20 MB upload limit

JOBS_DIR = Path("data/jobs")
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".rtf", ".md"}

# ── In-memory job store (thread-safe via Queue) ────────────────────────────────
_jobs: dict[str, dict] = {}
_job_queues: dict[str, queue.Queue] = {}


# ══════════════════════════════════════════════════════════════════════════════
# Helper
# ══════════════════════════════════════════════════════════════════════════════

def _allowed(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


# ══════════════════════════════════════════════════════════════════════════════
# Routes
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/config")
def api_config():
    """Let the frontend know whether an API key is already configured."""
    has_key = bool(os.getenv("ANTHROPIC_API_KEY", "").strip())
    return jsonify({"has_api_key": has_key})


@app.route("/api/process", methods=["POST"])
def process():
    """
    Accepts multipart/form-data with:
      resume     — file upload (PDF / DOCX / DOC / TXT)
      job_links  — newline-separated list of job URLs
      email      — optional recipient email address
    Returns {"job_id": "...", "total": N}
    """
    resume_file = request.files.get("resume")
    job_links_raw = request.form.get("job_links", "").strip()
    email = request.form.get("email", "").strip()

    # ── Validation ─────────────────────────────────────────────────────────────
    errors: list[str] = []
    if not resume_file or not resume_file.filename:
        errors.append("Please upload your resume file.")
    elif not _allowed(resume_file.filename):
        errors.append("Unsupported file type. Upload PDF, DOCX, DOC, or TXT.")

    links = [ln.strip() for ln in job_links_raw.splitlines() if ln.strip()]
    if not links:
        errors.append("Please enter at least one job link.")
    if len(links) > 20:
        errors.append("Maximum 20 job links per run.")

    if errors:
        return jsonify({"error": "\n".join(errors)}), 400

    # ── Create job workspace ────────────────────────────────────────────────────
    job_id = str(uuid.uuid4())
    job_dir = JOBS_DIR / job_id
    output_dir = job_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    safe_name = secure_filename(resume_file.filename)
    resume_path = job_dir / safe_name
    resume_file.save(str(resume_path))

    links_path = job_dir / "job_links.txt"
    links_path.write_text("\n".join(links), encoding="utf-8")

    # ── Register job ────────────────────────────────────────────────────────────
    q: queue.Queue = queue.Queue()
    _jobs[job_id] = {"status": "queued", "links": links, "email": email, "pdfs": []}
    _job_queues[job_id] = q

    threading.Thread(
        target=_run_job,
        args=(job_id, resume_path, links_path, output_dir, email),
        daemon=True,
    ).start()

    return jsonify({"job_id": job_id, "total": len(links)})


@app.route("/api/status/<job_id>")
def job_status(job_id: str):
    """Server-Sent Events stream for real-time job progress."""

    def generate():
        if job_id not in _jobs:
            yield _sse({"type": "error", "message": "Job not found."})
            return
        q = _job_queues.get(job_id)
        if q is None:
            yield _sse({"type": "error", "message": "Job queue missing."})
            return

        while True:
            try:
                msg = q.get(timeout=28)
            except queue.Empty:
                yield _sse({"type": "ping"})
                continue
            yield _sse(msg)
            if msg.get("type") in ("complete", "error"):
                break

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/download/<job_id>/<filename>")
def download_pdf(job_id: str, filename: str):
    """Securely serve a generated PDF for download."""
    safe_name = Path(secure_filename(filename)).name
    pdf_path = (JOBS_DIR / job_id / "output" / safe_name).resolve()

    # Ensure the resolved path is inside JOBS_DIR (prevent path traversal)
    try:
        pdf_path.relative_to(JOBS_DIR.resolve())
    except ValueError:
        return jsonify({"error": "Invalid path."}), 403

    if not pdf_path.exists() or pdf_path.suffix.lower() != ".pdf":
        return jsonify({"error": "File not found."}), 404

    return send_file(str(pdf_path), as_attachment=True, download_name=safe_name)


# ══════════════════════════════════════════════════════════════════════════════
# Background worker
# ══════════════════════════════════════════════════════════════════════════════

def _push(q: queue.Queue, msg: dict) -> None:
    q.put(msg)


def _run_job(
    job_id: str,
    resume_path: Path,
    links_path: Path,
    output_dir: Path,
    email: str,
) -> None:
    q = _job_queues[job_id]

    try:
        # Lazy imports — avoids loading heavy modules at startup
        from src.data.profile_loader import load_profile
        from src.emailer import send_results_email
        from src.extractors.job_parser import JobFetchError, load_job_sources, parse_job_source
        from src.extractors.resume_parser import parse_resume_text
        from src.llm.anthropic_client import ResumeGenerator
        from src.postprocess.resume_optimizer import optimize_resume
        from src.renderers.docx_resume import render_resume_docx
        from src.renderers.pdf_resume import render_resume_pdf
        from src.scoring.ats_keywords import overlap_score
        from src.settings import get_settings
        from src.utils.slug import slugify

        settings = get_settings()

        if not settings.anthropic_api_key:
            _push(q, {
                "type": "error",
                "message": (
                    "Claude API key is not configured. "
                    "Enter it in the form or add ANTHROPIC_API_KEY to your .env file."
                ),
            })
            return

        # ── Parse uploaded resume ───────────────────────────────────────────────
        _push(q, {"type": "status", "message": "Reading your resume..."})
        try:
            base_text = parse_resume_text(resume_path)
        except Exception as exc:
            _push(q, {"type": "error", "message": f"Could not read your resume: {exc}"})
            return

        # ── Load job links ──────────────────────────────────────────────────────
        _push(q, {"type": "status", "message": "Loading job listings..."})
        job_sources = load_job_sources(links_path)
        total = len(job_sources)

        if total == 0:
            _push(q, {"type": "error", "message": "No valid job links were found."})
            return

        _push(q, {"type": "total", "total": total,
                  "message": f"Found {total} job link(s). Tailoring your resume for each one..."})

        profile = load_profile(None)
        generator = ResumeGenerator(settings, Path("prompts/resume_prompt.txt"))
        pdf_files: list[Path] = []

        for idx, source in enumerate(job_sources, start=1):
            # ── Fetch job ───────────────────────────────────────────────────────
            _push(q, {
                "type": "progress",
                "current": idx,
                "total": total,
                "message": f"Fetching job {idx} of {total}...",
                "source": str(source),
            })

            try:
                job = parse_job_source(source, timeout=settings.request_timeout_seconds)
            except JobFetchError as exc:
                _push(q, {
                    "type": "job_result",
                    "current": idx,
                    "total": total,
                    "success": False,
                    "source": str(source),
                    "company": "Unknown",
                    "title": "Unknown",
                    "message": f"Skipped — could not fetch job: {exc}",
                })
                continue

            pre_score, _ = overlap_score(base_text, job.text)

            # ── Generate resume ─────────────────────────────────────────────────
            _push(q, {
                "type": "progress",
                "current": idx,
                "total": total,
                "message": (
                    f"Generating tailored resume for "
                    f"{job.company or 'company'} — {job.title or 'position'}..."
                ),
                "source": str(source),
            })

            try:
                tailored = generator.generate(
                    base_resume_text=base_text,
                    job=job,
                    candidate_name=profile.name,
                    profile=profile,
                )
            except Exception as exc:
                _push(q, {
                    "type": "job_result",
                    "current": idx,
                    "total": total,
                    "success": False,
                    "source": str(source),
                    "company": job.company or "Unknown",
                    "title": job.title or "Unknown",
                    "message": f"AI generation failed — {exc}",
                })
                continue

            tailored = optimize_resume(tailored, profile=profile)

            resume_score_text = "\n".join([
                tailored.summary,
                " ".join(tailored.skills),
                " ".join(b for e in tailored.experience for b in e.bullets),
                " ".join(b for e in tailored.experience for s in e.sections for b in s.bullets),
            ])
            post_score, _ = overlap_score(resume_score_text, job.text)

            # ── Render PDF + DOCX ───────────────────────────────────────────────
            company_slug = slugify(job.company or "company")
            title_slug = slugify(job.title or tailored.target_title or "role")
            base_name = f"{company_slug}_{title_slug}_resume"

            pdf_path = output_dir / f"{base_name}.pdf"
            render_resume_pdf(tailored, pdf_path)
            pdf_files.append(pdf_path)

            docx_path = output_dir / f"{base_name}.docx"
            try:
                render_resume_docx(tailored, docx_path)
            except Exception:
                docx_path = None   # DOCX failure is non-fatal

            _push(q, {
                "type": "job_result",
                "current": idx,
                "total": total,
                "success": True,
                "source": str(source),
                "company": job.company or "Unknown",
                "title": job.title or tailored.target_title or "Unknown",
                "filename": pdf_path.name,
                "docx_filename": docx_path.name if docx_path else None,
                "job_id": job_id,
                "pre_score": round(pre_score * 100),
                "post_score": round(post_score * 100),
                "message": f"Resume created — PDF + DOCX",
            })

        # ── Email delivery ──────────────────────────────────────────────────────
        if email and pdf_files:
            if settings.smtp_host:
                _push(q, {"type": "status",
                          "message": f"Sending {len(pdf_files)} PDF(s) to {email}..."})
                try:
                    send_results_email(
                        settings=settings,
                        to_address=email,
                        subject=(
                            f"ResumeForge AI — {len(pdf_files)} Tailored Resume(s) Ready"
                        ),
                        body=(
                            f"Hi,\n\n"
                            f"Your ATS-optimised tailored resume(s) are attached.\n\n"
                            f"Generated {len(pdf_files)} resume(s) across {total} job(s).\n\n"
                            f"— ResumeForge AI"
                        ),
                        attachments=pdf_files,
                    )
                    _push(q, {"type": "status",
                              "message": f"Resumes sent to {email} successfully."})
                except Exception as exc:
                    _push(q, {"type": "status",
                              "message": f"Email delivery failed: {exc}. Download below."})
            else:
                _push(q, {"type": "status",
                          "message": "Email not configured — download your PDFs directly below."})

        # ── Completion ──────────────────────────────────────────────────────────
        _jobs[job_id]["pdfs"] = [f.name for f in pdf_files]
        _jobs[job_id]["status"] = "complete"

        _push(q, {
            "type": "complete",
            "total_generated": len(pdf_files),
            "total_jobs": total,
            "message": (
                f"All done! Generated {len(pdf_files)} tailored resume(s) "
                f"from {total} job link(s)."
            ),
        })

    except Exception as exc:
        _jobs[job_id]["status"] = "error"
        _push(q, {
            "type": "error",
            "message": f"Unexpected error: {exc}",
            "detail": traceback.format_exc(),
        })


# ══════════════════════════════════════════════════════════════════════════════
# Entrypoint
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    print()
    print("=" * 60)
    print("  ResumeForge AI  —  Web Application")
    print("=" * 60)
    print("  Open:  http://localhost:5000")
    print("=" * 60)
    print()
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port, threaded=True)
