from __future__ import annotations

import zipfile
from pathlib import Path

from docx import Document
from pypdf import PdfReader


class ResumeParseError(RuntimeError):
    pass


SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".doc", ".txt", ".md", ".rtf")


def resolve_resume_path(path: Path | None, search_root: Path | None = None) -> Path:
    if path and path.exists():
        return path

    candidates: list[Path] = []
    roots = [search_root] if search_root else []
    roots.extend([Path("data/input"), Path(".")])

    seen: set[str] = set()
    for root in roots:
        if not root or not root.exists():
            continue
        for ext in SUPPORTED_EXTENSIONS:
            for candidate in sorted(root.glob(f"*{ext}")):
                key = str(candidate.resolve())
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(candidate)

    if candidates:
        return candidates[0]

    hint = path.as_posix() if path else "data/input/resume.docx"
    raise ResumeParseError(
        "Resume file not found. Put your resume in data/input/ or pass --resume explicitly. "
        f"Expected path example: {hint}"
    )


def parse_resume_text(path: Path) -> str:
    path = resolve_resume_path(path, path.parent if path else None)

    detected = _detect_kind(path)
    if detected == "pdf":
        return _read_pdf(path)
    if detected == "docx":
        return _read_docx(path)
    if detected == "text":
        return path.read_text(encoding="utf-8", errors="ignore").strip()
    raise ResumeParseError(
        "Unsupported resume format. Use a real .pdf, .docx, .doc, .txt, .md, or .rtf file. "
        f"Detected: {path.suffix or 'unknown'}"
    )


def _detect_kind(path: Path) -> str:
    header = path.read_bytes()[:8]
    suffix = path.suffix.lower()
    if header.startswith(b"%PDF-"):
        return "pdf"
    if header.startswith(b"PK") and zipfile.is_zipfile(path):
        return "docx"
    if suffix in {".txt", ".md", ".doc", ".rtf"}:
        return "text"
    if suffix == ".pdf":
        raise ResumeParseError(
            f"{path.name} is not a valid PDF. Export your resume again as a real PDF from Word or Google Docs, "
            "or point --resume to the original .docx file instead."
        )
    if suffix == ".docx":
        return "docx"
    try:
        path.read_text(encoding="utf-8")
        return "text"
    except UnicodeDecodeError:
        return "unknown"


def _read_pdf(path: Path) -> str:
    try:
        reader = PdfReader(str(path))
    except Exception as exc:
        raise ResumeParseError(
            f"Could not read PDF resume '{path.name}'. Export a fresh PDF or use the .docx file instead."
        ) from exc

    parts: list[str] = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    text = "\n".join(parts).strip()
    if not text:
        raise ResumeParseError(
            f"The PDF '{path.name}' did not contain extractable text. Use a text-based PDF or a .docx resume."
        )
    return text


def _read_docx(path: Path) -> str:
    doc = Document(str(path))
    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip()).strip()
    if not text:
        raise ResumeParseError(f"The DOCX '{path.name}' appears empty.")
    return text
