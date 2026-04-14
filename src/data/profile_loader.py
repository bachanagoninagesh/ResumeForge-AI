from __future__ import annotations

import json
from pathlib import Path

from src.models import ProfileOverrides


class ProfileLoadError(RuntimeError):
    pass


def load_profile(path: Path | None) -> ProfileOverrides:
    if path is None or not path.exists():
        return ProfileOverrides()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProfileLoadError(f"Invalid JSON in profile file: {path}") from exc
    return ProfileOverrides.model_validate(data)
