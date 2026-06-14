from __future__ import annotations

import hashlib
from pathlib import Path

CHUNK_SIZE = 1024 * 1024


def normalize_source_path(path: Path) -> str:
    return path.resolve().as_posix()


def compute_source_path_hash(normalized_path: str) -> str:
    return hashlib.sha256(normalized_path.encode("utf-8")).hexdigest()


def compute_file_sha256(path: Path, chunk_size: int = CHUNK_SIZE) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def make_file_instance_uid(source_path_hash: str) -> str:
    return source_path_hash


def make_content_uid(sha256: str) -> str:
    return sha256
