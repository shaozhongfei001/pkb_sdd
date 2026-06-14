from __future__ import annotations

import mimetypes
from pathlib import Path

CANDIDATE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".pdf",
        ".docx",
        ".pptx",
        ".xlsx",
        ".doc",
        ".ppt",
        ".xls",
        ".png",
        ".jpg",
        ".jpeg",
        ".tiff",
        ".bmp",
        ".html",
        ".htm",
        ".xml",
        ".json",
        ".txt",
        ".md",
        ".csv",
    }
)

SKIP_DIR_NAMES: frozenset[str] = frozenset(
    {
        ".git",
        ".venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        "node_modules",
    }
)


def should_skip_dir(name: str) -> bool:
    return name in SKIP_DIR_NAMES


def is_candidate_file(path: Path) -> bool:
    if not path.is_file():
        return False
    return path.suffix.lower() in CANDIDATE_EXTENSIONS


def guess_mime_type(path: Path) -> str | None:
    mime_type, _ = mimetypes.guess_type(path.name)
    return mime_type
