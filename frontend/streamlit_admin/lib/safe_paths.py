from __future__ import annotations

from pathlib import Path

ALLOWED_TEXT_SUFFIXES = frozenset({".md", ".json", ".txt", ".markdown"})


class PathTraversalError(ValueError):
    """Raised when a candidate path escapes its configured root."""


def resolve_under_root(root: Path, candidate: str | Path) -> Path:
    """Resolve candidate relative to root; reject traversal and symlinks."""
    resolved_root = root.resolve()
    candidate_path = Path(candidate)

    if candidate_path.is_absolute():
        raise PathTraversalError("absolute paths are not allowed")

    if ".." in candidate_path.parts:
        raise PathTraversalError("path traversal via '..' is not allowed")

    resolved = (resolved_root / candidate_path).resolve()

    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise PathTraversalError(
            f"path escapes root: {candidate!r} under {resolved_root}"
        ) from exc

    if resolved.is_symlink():
        raise PathTraversalError("symlinks are not allowed")

    return resolved


def read_text_under_root(root: Path, relative_path: str | Path) -> str:
    """Read UTF-8 text from a path guarded by resolve_under_root."""
    path = resolve_under_root(root, relative_path)
    if path.suffix.lower() not in ALLOWED_TEXT_SUFFIXES:
        raise PathTraversalError(
            f"unsupported file type: {path.suffix!r}; allowed: {sorted(ALLOWED_TEXT_SUFFIXES)}"
        )
    return path.read_text(encoding="utf-8")
