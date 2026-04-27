from __future__ import annotations

import re
from importlib import metadata
from pathlib import Path
from typing import Final


def _read_pyproject_version_fallback() -> str | None:
    candidate = Path(__file__).resolve().parent.parent / "pyproject.toml"
    if not candidate.exists():
        return None
    try:
        text = candidate.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return match.group(1) if match else None


def _resolve_version() -> str:
    try:
        return metadata.version("ifixai")
    except metadata.PackageNotFoundError:
        fallback = _read_pyproject_version_fallback()
        return fallback or "unknown"


VERSION: Final[str] = _resolve_version()
