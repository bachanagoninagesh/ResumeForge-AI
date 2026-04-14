from __future__ import annotations

import re


def slugify(text: str, max_length: int = 60) -> str:
    """Convert text to a safe lowercase filename slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", " ", text)   # remove punctuation
    text = re.sub(r"[\s_-]+", "_", text)     # spaces/dashes → underscore
    text = text.strip("_")
    return text[:max_length]
