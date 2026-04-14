"""
DOCX Resume Renderer — matches the reference resume visual style.

Visual design (mirrors pdf_resume.py):
  - Name: ALL CAPS, 22pt bold, centered, black
  - Contact line: centered 9pt; LinkedIn/GitHub in blue
  - Section headers: bold blue #2E5FA3, with bottom border rule
  - Project subheadings: italic
  - Bullets: justified, hanging indent
  - Skills: 2-column table, bold category labels
  - Education: degree bold black | school bold blue; dates italic right
  - White page background, Calibri font throughout
"""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

from src.models import TailoredResume

# ── Colours ───────────────────────────────────────────────────────────────────
BLUE  = RGBColor(0x2E, 0x5F, 0xA3)
BLACK = RGBColor(0x00, 0x00, 0x00)
DARK  = RGBColor(0x11, 0x11, 0x11)

# ── Font / size constants ──────────────────────────────────────────────────────
FONT         = "Calibri"
NAME_PT      = 22
CONTACT_PT   = 9.0
SECTION_PT   = 10.0
BODY_PT      = 9.5

# ── Page geometry (letter, matching pdf_resume.py margins) ────────────────────
PAGE_W   = Inches(8.5)
PAGE_H   = Inches(11)
MARGIN_L = Inches(0.60)
MARGIN_R = Inches(0.60)
MARGIN_T = Inches(0.38)
MARGIN_B = Inches(0.36)

# Content width = 8.5 - 0.6 - 0.6 = 7.3 inches
CONTENT_W = Inches(7.3)
HALF_W    = Inches(3.65)

# URL detector for contact line blue colouring
_URL_RE = re.compile(r"(https?://\S+|linkedin\.com\S*|github\.com\S*)", re.I)


# ══════════════════════════════════════════════════════════════════════════════
# Public entry point
# ══════════════════════════════════════════════════════════════════════════════

def render_resume_docx(resume: TailoredResume, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = _new_doc()

    # ── NAME ─────────────────────────────────────────────────────────────────
    name = (resume.contact.name or "Candidate").upper()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _sp(p, before=0, after=2)
    _run(p, name, size=NAME_PT, bold=True, color=BLACK)

    # ── CONTACT LINE ─────────────────────────────────────────────────────────
    parts = [x for x in [
        resume.contact.email, resume.contact.phone, resume.contact.location,
        resume.contact.linkedin, resume.contact.portfolio,
    ] if x]
    if parts:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _sp(p, before=0, after=3)
        for i, part in enumerate(parts):
            if i:
                _run(p, " | ", size=CONTACT_PT, color=DARK)
            color = BLUE if _URL_RE.search(part) else DARK
            _run(p, part, size=CONTACT_PT, color=color)

    # ── PROFESSIONAL SUMMARY ──────────────────────────────────────────────────
    if resume.summary:
        _section_header(doc, "PROFESSIONAL SUMMARY")
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.left_indent = Inches(0.04)
        _sp(p, before=0, after=2)
        _run(p, resume.summary, size=BODY_PT)

    # ── PROFESSIONAL EXPERIENCE ───────────────────────────────────────────────
    if resume.experience:
        _section_header(doc, "PROFESSIONAL EXPERIENCE")
        for exp in resume.experience:
            _add_experience(doc, exp)

    # ── TECHNICAL SKILLS ──────────────────────────────────────────────────────
    if resume.skills:
        _section_header(doc, "TECHNICAL SKILLS")
        _add_skills(doc, resume.skills)

    # ── CERTIFICATIONS ────────────────────────────────────────────────────────
    if resume.certifications:
        _section_header(doc, "CERTIFICATIONS")
        _add_certs(doc, resume.certifications)

    # ── EDUCATION ─────────────────────────────────────────────────────────────
    if resume.education:
        _section_header(doc, "EDUCATION")
        for edu in resume.education[:2]:
            _add_education(doc, edu)

    # ── LEADERSHIP & ACTIVITIES ───────────────────────────────────────────────
    if resume.activities:
        _section_header(doc, "LEADERSHIP & ACTIVITIES")
        for item in resume.activities:
            _add_activity(doc, item)

    # ── ACHIEVEMENTS & AWARDS ─────────────────────────────────────────────────
    if getattr(resume, "achievements", None):
        _section_header(doc, "ACHIEVEMENTS & AWARDS")
        for item in resume.achievements:
            t = (item or "").strip().lstrip("-•").strip()
            if t:
                _add_bullet(doc, t)

    # ── LANGUAGES ─────────────────────────────────────────────────────────────
    if getattr(resume, "languages", None):
        _section_header(doc, "LANGUAGES")
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.04)
        _sp(p, before=0, after=2)
        _run(p, "  •  ".join(l.strip() for l in resume.languages if l.strip()), size=BODY_PT)

    # ── PUBLICATIONS & PATENTS ────────────────────────────────────────────────
    if getattr(resume, "publications", None):
        _section_header(doc, "PUBLICATIONS & PATENTS")
        for item in resume.publications:
            t = (item or "").strip().lstrip("-•").strip()
            if t:
                _add_bullet(doc, t)

    doc.save(str(out_path))


# ══════════════════════════════════════════════════════════════════════════════
# Document setup
# ══════════════════════════════════════════════════════════════════════════════

def _new_doc() -> Document:
    doc = Document()
    sec = doc.sections[0]
    sec.page_width   = PAGE_W
    sec.page_height  = PAGE_H
    sec.left_margin  = MARGIN_L
    sec.right_margin = MARGIN_R
    sec.top_margin   = MARGIN_T
    sec.bottom_margin = MARGIN_B

    # Reset Normal style defaults
    ns = doc.styles["Normal"]
    ns.font.name = FONT
    ns.font.size = Pt(BODY_PT)
    ns.paragraph_format.space_before = Pt(0)
    ns.paragraph_format.space_after  = Pt(0)
    ns.paragraph_format.line_spacing = Pt(11.5)
    return doc


# ══════════════════════════════════════════════════════════════════════════════
# Section helpers
# ══════════════════════════════════════════════════════════════════════════════

def _section_header(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    _sp(p, before=5, after=0)
    _bottom_border(p)
    _run(p, text, size=SECTION_PT, bold=True, color=BLUE)


def _bottom_border(p, color: str = "2E5FA3", sz: int = 6) -> None:
    """Add a thin blue bottom border (rule) to a paragraph."""
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bot = OxmlElement("w:bottom")
    bot.set(qn("w:val"),   "single")
    bot.set(qn("w:sz"),    str(sz))
    bot.set(qn("w:space"), "1")
    bot.set(qn("w:color"), color)
    pBdr.append(bot)
    existing = pPr.find(qn("w:pBdr"))
    if existing is not None:
        pPr.remove(existing)
    pPr.append(pBdr)


# ══════════════════════════════════════════════════════════════════════════════
# Block renderers
# ══════════════════════════════════════════════════════════════════════════════

def _add_experience(doc: Document, exp) -> None:
    # Job title (bold left) — Dates (italic right) in a 2-col table
    t = _borderless_table(doc, cols=2, col_widths=[Inches(5.1), Inches(2.2)])
    lp = t.cell(0, 0).paragraphs[0]
    _sp(lp, before=4, after=0)
    _run(lp, exp.title or "", size=BODY_PT, bold=True)

    rp = t.cell(0, 1).paragraphs[0]
    rp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    _sp(rp, before=4, after=0)
    _run(rp, exp.dates or "", size=BODY_PT, italic=True)

    # Company | Location line
    co_loc = " | ".join(x for x in [exp.company, exp.location] if x)
    if co_loc:
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.04)
        _sp(p, before=1, after=1)
        _run(p, co_loc, size=BODY_PT, italic=True)

    # Top-level bullets
    for b in exp.bullets:
        t2 = b.strip().lstrip("-•").strip()
        if t2:
            _add_bullet(doc, t2)

    # Project subheadings (italic) + bullets
    for sec in exp.sections:
        if sec.name:
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.04)
            _sp(p, before=2, after=0)
            _run(p, sec.name, size=BODY_PT, italic=True)
        for b in sec.bullets:
            t2 = b.strip().lstrip("-•").strip()
            if t2:
                _add_bullet(doc, t2)

    # Small gap after each role
    _gap(doc, Pt(2))


def _add_skills(doc: Document, skills: list) -> None:
    parsed: list[tuple[str, str]] = []
    for s in skills:
        t = s.strip()
        if not t:
            continue
        if ":" in t:
            cat, vals = t.split(":", 1)
            parsed.append((cat.strip(), vals.strip()))
        else:
            parsed.append(("", t))
    if not parsed:
        return

    tbl = _borderless_table(doc, cols=2, col_widths=[HALF_W, HALF_W])
    # Remove the empty first row added by python-docx
    first_row = tbl.rows[0]

    for i in range(0, len(parsed), 2):
        lc, lv = parsed[i]
        rc, rv = parsed[i + 1] if i + 1 < len(parsed) else ("", "")

        if i == 0:
            row = first_row
        else:
            row = tbl.add_row()

        lp = row.cells[0].paragraphs[0]
        _sp(lp, before=0, after=1)
        if lc:
            _run(lp, lc + ": ", size=BODY_PT, bold=True)
        _run(lp, lv, size=BODY_PT)

        rp = row.cells[1].paragraphs[0]
        _sp(rp, before=0, after=1)
        if rc:
            _run(rp, rc + ": ", size=BODY_PT, bold=True)
        _run(rp, rv, size=BODY_PT)

    _gap(doc, Pt(2))


def _add_certs(doc: Document, certs: list) -> None:
    clean = [c.strip() for c in certs if c.strip()]
    for i in range(0, len(clean), 3):
        chunk = clean[i:i+3]
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.04)
        _sp(p, before=0, after=0)
        for j, cert in enumerate(chunk):
            if j:
                _run(p, "    •    ", size=BODY_PT)
            _run(p, cert, size=BODY_PT)
    _gap(doc, Pt(2))


def _add_education(doc: Document, edu) -> None:
    degree = (edu.degree or "").strip()
    school = (edu.school or "").strip()
    right_text = " | ".join(x for x in [edu.details, edu.dates] if x)

    tbl = _borderless_table(doc, cols=2, col_widths=[Inches(4.4), Inches(2.9)])

    lp = tbl.cell(0, 0).paragraphs[0]
    _sp(lp, before=2, after=2)
    if degree:
        _run(lp, degree, size=BODY_PT, bold=True)
    if degree and school:
        _run(lp, " | ", size=BODY_PT)
    if school:
        _run(lp, school, size=BODY_PT, bold=True, color=BLUE)

    rp = tbl.cell(0, 1).paragraphs[0]
    rp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    _sp(rp, before=2, after=2)
    _run(rp, right_text, size=BODY_PT, italic=True)


def _add_activity(doc: Document, item) -> None:
    name  = item.name  or ""
    dates = item.dates or ""
    if dates:
        tbl = _borderless_table(doc, cols=2, col_widths=[Inches(5.1), Inches(2.2)])
        lp = tbl.cell(0, 0).paragraphs[0]
        _sp(lp, before=0, after=1)
        _run(lp, f"• {name}", size=BODY_PT)

        rp = tbl.cell(0, 1).paragraphs[0]
        rp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        _sp(rp, before=0, after=1)
        _run(rp, dates, size=BODY_PT, italic=True)
    else:
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.04)
        _sp(p, before=0, after=1)
        _run(p, f"• {name}", size=BODY_PT)


def _add_bullet(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.left_indent      = Inches(0.22)
    p.paragraph_format.first_line_indent = Inches(-0.10)
    _sp(p, before=0, after=0.8)
    _run(p, "• ", size=BODY_PT)
    # Bold inline text marked with **...**
    for part in re.split(r"(\*\*[^*]+\*\*)", text):
        if part.startswith("**") and part.endswith("**"):
            _run(p, part[2:-2], size=BODY_PT, bold=True)
        else:
            _run(p, part, size=BODY_PT)


# ══════════════════════════════════════════════════════════════════════════════
# Low-level helpers
# ══════════════════════════════════════════════════════════════════════════════

def _run(
    p,
    text: str,
    size: float = BODY_PT,
    bold: bool = False,
    italic: bool = False,
    color: RGBColor = BLACK,
) -> None:
    r = p.add_run(text)
    r.font.name   = FONT
    r.font.size   = Pt(size)
    r.font.bold   = bold
    r.font.italic = italic
    r.font.color.rgb = color


def _sp(p, before: float = 0, after: float = 0) -> None:
    p.paragraph_format.space_before  = Pt(before)
    p.paragraph_format.space_after   = Pt(after)
    p.paragraph_format.line_spacing  = Pt(11.5)


def _gap(doc: Document, size: Pt) -> None:
    p = doc.add_paragraph()
    _sp(p, before=0, after=0)
    p.paragraph_format.line_spacing = size


def _borderless_table(doc: Document, cols: int, col_widths: list) -> object:
    """Create a table with no visible borders and specified column widths."""
    tbl = doc.add_table(rows=1, cols=cols)

    # Remove all table borders via XML
    tblPr = tbl._tbl.find(qn("w:tblPr"))
    if tblPr is None:
        tblPr = OxmlElement("w:tblPr")
        tbl._tbl.insert(0, tblPr)
    borders = OxmlElement("w:tblBorders")
    for name in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{name}")
        el.set(qn("w:val"),   "none")
        el.set(qn("w:sz"),    "0")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "auto")
        borders.append(el)
    existing = tblPr.find(qn("w:tblBorders"))
    if existing is not None:
        tblPr.remove(existing)
    tblPr.append(borders)

    # Set column widths
    for i, w in enumerate(col_widths):
        tbl.columns[i].width = w
        for cell in tbl.column_cells(i):
            cell.width = w

    return tbl
