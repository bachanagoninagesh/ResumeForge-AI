from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from src.data.profile_loader import ProfileLoadError, load_profile
from src.emailer import EmailConfigurationError, send_results_email
from src.extractors.job_parser import JobFetchError, JobSourceError, load_job_sources, parse_job_source
from src.extractors.resume_parser import ResumeParseError, parse_resume_text, resolve_resume_path
from src.llm.anthropic_client import ResumeGenerator
from src.postprocess.resume_optimizer import optimize_resume
from src.renderers.pdf_resume import render_resume_pdf
from src.scoring.ats_keywords import overlap_score
from src.settings import get_settings
from src.utils.slug import slugify


def main() -> None:
    load_dotenv()
    args = parse_args()
    settings = get_settings()

    requested_resume_path = Path(args.resume) if args.resume else None
    jobs_path = Path(args.jobs)
    out_dir = Path(args.out)
    profile_path = Path(args.profile) if args.profile else None
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        resume_path = resolve_resume_path(requested_resume_path, Path("data/input"))
        base_resume_text = parse_resume_text(resume_path)
        profile = load_profile(profile_path)
        job_sources = load_job_sources(jobs_path)
    except (ResumeParseError, ProfileLoadError, JobSourceError) as exc:
        raise SystemExit(str(exc)) from exc

    if args.max_jobs:
        job_sources = job_sources[: args.max_jobs]

    print(f"Using resume: {resume_path}")
    if profile_path and profile_path.exists():
        print(f"Using profile: {profile_path}")
    print(f"Jobs to process: {len(job_sources)}")

    generator = ResumeGenerator(settings, Path("prompts/resume_prompt.txt"))
    pdf_files: list[Path] = []

    for idx, source in enumerate(job_sources, start=1):
        print(f"[{idx}/{len(job_sources)}] Processing: {source}")
        try:
            job = parse_job_source(source, timeout=settings.request_timeout_seconds)
        except JobFetchError as exc:
            print(f"  -> SKIPPED: {exc}")
            continue
        pre_score, _ = overlap_score(base_resume_text, job.text)

        tailored = generator.generate(
            base_resume_text=base_resume_text,
            job=job,
            candidate_name=args.name or profile.name,
            profile=profile,
        )
        tailored = optimize_resume(tailored, profile=profile)

        resume_text_for_score = "\n".join([
            tailored.summary,
            " ".join(tailored.skills),
            " ".join(b for e in tailored.experience for b in e.bullets),
            " ".join(b for e in tailored.experience for s in e.sections for b in s.bullets),
            " ".join(f"{a.name} {a.dates}" for a in tailored.activities),
        ])
        post_score, _ = overlap_score(resume_text_for_score, job.text)

        company_slug = slugify(job.company or "company")
        title_slug = slugify(job.title or tailored.target_title or "role")
        stem = f"{company_slug}_{title_slug}_resume"

        pdf_path = out_dir / f"{stem}.pdf"
        render_resume_pdf(tailored, pdf_path)
        pdf_files.append(pdf_path)

        print(f"  -> ATS score before: {pre_score:.0%}  |  after: {post_score:.0%}")
        print(f"  -> PDF: {pdf_path.name}")

    email_to = args.email_to or settings.default_email_to
    if email_to and pdf_files and settings.smtp_host:
        try:
            send_results_email(
                settings=settings,
                to_address=email_to,
                subject=f"Tailored Resume{'s' if len(pdf_files) > 1 else ''} ({len(pdf_files)} PDF{'s' if len(pdf_files) > 1 else ''})",
                body=(
                    f"Hi,\n\n"
                    f"Please find attached your ATS-tailored resume{'s' if len(pdf_files) > 1 else ''}.\n\n"
                    f"{'Files attached:' if len(pdf_files) > 1 else 'File attached:'}\n"
                    + "\n".join(f"  - {p.name}" for p in pdf_files)
                    + "\n\nGenerated using the same ATS-safe layout for all roles.\n"
                ),
                attachments=pdf_files,
            )
            print(f"\n  -> Emailed {len(pdf_files)} PDF(s) to {email_to}")
        except EmailConfigurationError as exc:
            print(f"\n  -> Skipped email: {exc}")
        except Exception as exc:
            print(f"\n  -> Email failed, but resumes were generated successfully: {exc}")

    print(f"\nDone. {len(pdf_files)} PDF resume(s) saved to: {out_dir.resolve()}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate one-page ATS-friendly PDF resumes from job links."
    )
    parser.add_argument(
        "--resume",
        default="data/input/Resume.doc",
        help="Path to base resume (.pdf, .docx, .doc, .txt)",
    )
    parser.add_argument(
        "--jobs",
        default="data/input/job_links.txt",
        help="Path to txt file with job URLs or local job-description file paths",
    )
    parser.add_argument("--out", default="data/output", help="Output directory (PDFs only)")
    parser.add_argument(
        "--profile",
        default="data/input/profile.json",
        help="JSON file with personal detail overrides",
    )
    parser.add_argument("--name", default="", help="Optional preferred name override")
    parser.add_argument("--max-jobs", type=int, default=0, help="Limit number of jobs to process")
    parser.add_argument(
        "--email-to",
        default="",
        help="Email address to send PDF resume(s) to",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
