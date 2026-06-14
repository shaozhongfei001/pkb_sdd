from __future__ import annotations

from pathlib import Path

DOCUMENT_EXTENSIONS = frozenset(
    {
        ".txt",
        ".csv",
        ".md",
        ".markdown",
        ".html",
        ".htm",
        ".xml",
        ".json",
        ".pdf",
        ".doc",
        ".docx",
        ".ppt",
        ".pptx",
        ".xls",
        ".xlsx",
        ".png",
        ".jpg",
        ".jpeg",
        ".tiff",
        ".bmp",
        ".gif",
        ".webp",
        ".rtf",
        ".odt",
        ".ods",
        ".odp",
    }
)

SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        ".svn",
        ".hg",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".venv",
        "venv",
        "node_modules",
        ".idea",
        ".vscode",
        "raw_vault",
        "parsed",
        "curated",
        "quarantine",
        "reports",
    }
)

_MIME_BY_EXT = {
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".html": "text/html",
    ".htm": "text/html",
    ".xml": "application/xml",
    ".json": "application/json",
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ),
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


def should_skip_dir(name: str) -> bool:
    return name in SKIP_DIR_NAMES


def is_document_candidate(path: Path) -> bool:
    if not path.is_file():
        return False
    return path.suffix.lower() in DOCUMENT_EXTENSIONS


def guess_mime_type(path: Path) -> str | None:
    return _MIME_BY_EXT.get(path.suffix.lower())
