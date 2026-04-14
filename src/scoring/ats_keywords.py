from __future__ import annotations

import re
from collections import Counter


def _tokenize(text: str) -> list[str]:
    """Lowercase alphabetic tokens, length >= 3."""
    return [w for w in re.findall(r"[a-z]{3,}", text.lower()) if w]


# Common English stop-words to exclude from keyword matching
_STOP = {
    "the", "and", "for", "are", "with", "this", "that", "have", "will",
    "from", "they", "been", "their", "has", "was", "were", "you", "your",
    "our", "not", "but", "can", "all", "any", "may", "use", "used", "using",
    "also", "such", "than", "each", "more", "other", "both", "its", "into",
    "able", "well", "when", "who", "how", "what", "which", "within", "across",
}


def overlap_score(resume_text: str, job_text: str) -> tuple[float, list[str]]:
    """
    Returns (score 0-1, list of matched keywords).
    Score = fraction of unique job keywords found in resume text.
    """
    job_tokens  = {t for t in _tokenize(job_text)  if t not in _STOP}
    res_tokens  = {t for t in _tokenize(resume_text) if t not in _STOP}

    if not job_tokens:
        return 0.0, []

    matched = sorted(job_tokens & res_tokens)
    score   = len(matched) / len(job_tokens)
    return score, matched
