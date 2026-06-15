from __future__ import annotations

from pathlib import Path
from typing import TypedDict

VAULT_NOT_COPIED = "NOT_COPIED"
VAULT_COPIED = "COPIED"
VAULT_COPY_ERROR = "COPY_ERROR"

COPY_PENDING = "PENDING"
COPY_COPIED = "COPIED"
COPY_ERROR = "ERROR"

CHUNK_SIZE = 1024 * 1024


class VaultArtifactPaths(TypedDict):
    vault_dir: Path
    original_bin: Path
    original_name: Path
    source_paths_json: Path
    file_metadata_json: Path


def vault_uid_for(sha256: str) -> str:
    return sha256


def build_vault_dir(raw_vault_root: Path, sha256: str) -> Path:
    prefix = sha256[:2].lower()
    return raw_vault_root / "by_hash" / prefix / sha256


def build_vault_artifact_paths(vault_dir: Path) -> VaultArtifactPaths:
    return VaultArtifactPaths(
        vault_dir=vault_dir,
        original_bin=vault_dir / "original.bin",
        original_name=vault_dir / "original_name.txt",
        source_paths_json=vault_dir / "source_paths.json",
        file_metadata_json=vault_dir / "file_metadata.json",
    )
