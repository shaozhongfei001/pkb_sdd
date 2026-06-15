from __future__ import annotations

from pathlib import Path
from typing import TypedDict


class ParsedArtifactPaths(TypedDict):
    parsed_dir: Path
    parsed_text: Path
    parsed_metadata: Path
    parse_manifest: Path


def build_parsed_content_dir(parsed_root: Path, sha256: str) -> Path:
    prefix_a = sha256[:2].lower()
    prefix_b = sha256[2:4].lower()
    return parsed_root / "by_hash" / prefix_a / prefix_b / sha256


def build_parsed_artifact_paths(parsed_dir: Path) -> ParsedArtifactPaths:
    return ParsedArtifactPaths(
        parsed_dir=parsed_dir,
        parsed_text=parsed_dir / "parsed_text.md",
        parsed_metadata=parsed_dir / "parsed_metadata.json",
        parse_manifest=parsed_dir / "parse_manifest.json",
    )
