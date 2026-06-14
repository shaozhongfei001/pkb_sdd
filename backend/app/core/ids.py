from __future__ import annotations

import hashlib
from pathlib import Path

CHUNK_SIZE = 1024 * 1024


def normalize_path(path: Path) -> Path:
    return path.expanduser().resolve()


def compute_source_path_hash(path: Path) -> str:
    normalized = normalize_path(path).as_posix()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def compute_sha256(path: Path, chunk_size: int = CHUNK_SIZE) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()
