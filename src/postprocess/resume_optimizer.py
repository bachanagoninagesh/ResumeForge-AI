from __future__ import annotations

import re

from src.models import ProfileOverrides, TailoredResume

MAX_SKILLS = 6
MAX_CERTIFICATIONS = 6
MAX_ATS_KEYWORDS = 30
MAX_NOTES = 8

MAX_EXPERIENCE_ROLES = 2
MAX_BULLETS_PER_ROLE = 0       # all bullets go under subheadings — none at role level
MAX_SECTION_BULLETS = 3        # exactly 3 bullets per subheading
MAX_BULLET_CHARS = 145         # ~130 char target; 145 hard cap

MAX_PROJECTS = 0
MAX_PROJECT_BULLETS = 3
MAX_PROJECT_BULLET_CHARS = 145
MAX_ACTIVITIES = 2             # keep activities tight for 1-page fit

ACTION_VERBS = {
    "built", "developed", "designed", "engineered", "implemented", "created", "optimized",
    "streamlined", "automated", "delivered", "authored", "performed", "validated", "collaborated",
    "provided", "managed", "improved", "deployed", "resolved", "analyzed", "led", "supported",
}


def optimize_resume(resume: TailoredResume, profile: ProfileOverrides | None = None) -> TailoredResume:
    profile = profile or ProfileOverrides()
    resume = TailoredResume.model_validate(resume.model_dump())

    _apply_profile(resume, profile)

    resume.target_title = _limit_text(_squash_whitespace(resume.target_title), 120)
    resume.summary = _limit_text(_squash_whitespace(resume.summary), 300)
    resume.skills = _dedupe([_squash_whitespace(s) for s in resume.skills], limit=MAX_SKILLS)
    # Strip NCC / National Cadet Corps — not a professional certification
    _NCC_FILTER = re.compile(r"national cadet corps|\bncc\b", re.IGNORECASE)
    resume.certifications = _dedupe(
        [_squash_whitespace(s) for s in resume.certifications
         if not _NCC_FILTER.search(s)],
        limit=MAX_CERTIFICATIONS
    )
    resume.activities = [a for a in resume.activities if a.name][:MAX_ACTIVITIES]
    for a in resume.activities:
        a.name = _limit_text(_squash_whitespace(a.name), 80)
        a.dates = _limit_text(_squash_whitespace(a.dates), 30)

    # Always clear achievements — not rendered, frees page space
    resume.achievements = []
    resume.languages = _dedupe(
        [_limit_text(_squash_whitespace(s), 60) for s in resume.languages if s.strip()], limit=10
    )
    resume.publications = _dedupe(
        [_limit_text(_squash_whitespace(s), 220) for s in resume.publications if s.strip()], limit=6
    )

    resume.ats_keywords_used = _dedupe(
        [_squash_whitespace(s) for s in resume.ats_keywords_used], limit=MAX_ATS_KEYWORDS
    )
    resume.notes = _dedupe([_squash_whitespace(s) for s in resume.notes], limit=MAX_NOTES)

    for item in resume.experience:
        item.title = _limit_text(_squash_whitespace(item.title), 70)
        item.company = _limit_text(_squash_whitespace(item.company), 70)
        item.location = _limit_text(_squash_whitespace(item.location), 50)
        item.dates = _limit_text(_squash_whitespace(item.dates), 35)
        item.bullets = _trim_bullets(
            item.bullets, max_bullets=MAX_BULLETS_PER_ROLE, max_chars=MAX_BULLET_CHARS
        )
        item.sections = [s for s in item.sections if s.name or s.bullets][:2]
        for section in item.sections:
            section.name = _limit_text(_squash_whitespace(section.name), 70)
            section.bullets = _trim_bullets(
                section.bullets, max_bullets=MAX_SECTION_BULLETS, max_chars=MAX_BULLET_CHARS
            )

    for item in resume.projects:
        item.name = _limit_text(_squash_whitespace(item.name), 80)
        item.subtitle = _limit_text(_squash_whitespace(item.subtitle), 100)
        item.bullets = _trim_bullets(
            item.bullets, max_bullets=MAX_PROJECT_BULLETS, max_chars=MAX_PROJECT_BULLET_CHARS
        )

    for item in resume.education:
        item.school = _limit_text(_squash_whitespace(item.school), 70)
        item.degree = _limit_text(_squash_whitespace(item.degree), 80)
        item.location = _limit_text(_squash_whitespace(item.location), 50)
        item.dates = _limit_text(_squash_whitespace(item.dates), 35)
        item.details = _limit_text(_squash_whitespace(item.details), 80)

    resume.experience = [
        item for item in resume.experience if item.title or item.company or item.bullets or item.sections
    ][:MAX_EXPERIENCE_ROLES]
    resume.projects = []
    resume.education = [
        item for item in resume.education if item.school or item.degree
    ][:2]

    return resume


def _apply_profile(resume: TailoredResume, profile: ProfileOverrides) -> None:
    if profile.name:
        resume.contact.name = profile.name
    if profile.email:
        resume.contact.email = profile.email
    if profile.phone:
        resume.contact.phone = profile.phone
    if profile.location:
        resume.contact.location = profile.location
    if profile.linkedin:
        resume.contact.linkedin = profile.linkedin
    if profile.portfolio:
        resume.contact.portfolio = profile.portfolio
    if profile.summary_override and not resume.summary:
        resume.summary = profile.summary_override.strip()
    if not resume.target_title and profile.target_roles:
        resume.target_title = profile.target_roles[0]


def _trim_bullets(bullets: list[str], max_bullets: int, max_chars: int) -> list[str]:
    cleaned: list[str] = []
    for bullet in bullets:
        text = _limit_text(_squash_whitespace(re.sub(r"^[\-•\s]+", "", bullet)), max_chars)
        if not text:
            continue
        if text.split(" ", 1)[0].lower() not in ACTION_VERBS:
            text = text[0].upper() + text[1:] if text else text
        if text[-1] not in ".!?":
            text += "."
        cleaned.append(text)
        if len(cleaned) >= max_bullets:
            break
    return cleaned


def _squash_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip(" ,;|-\n\t")


def _limit_text(text: str, max_chars: int) -> str:
    text = _squash_whitespace(text)
    if len(text) <= max_chars:
        return text
    clipped = text[: max_chars + 1]
    last_space = clipped.rfind(" ")
    if last_space > max_chars * 0.6:
        clipped = clipped[:last_space]
    else:
        clipped = clipped[:max_chars]
    return clipped.rstrip(" ,;:-")


def _dedupe(items: list[str], limit: int) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = _squash_whitespace(item).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(_squash_whitespace(item))
        if len(out) >= limit:
            break
    return out
