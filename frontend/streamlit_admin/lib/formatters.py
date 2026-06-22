from __future__ import annotations

from datetime import datetime
from typing import Any

from app.schemas.search import SearchHit


def truncate_text(text: str | None, max_len: int = 200) -> str:
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def format_datetime(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.strftime("%Y-%m-%d %H:%M:%S")


def hit_display_name(hit: SearchHit) -> str:
    meta = hit.metadata or {}
    for key in ("title", "asset_title", "project_name", "project_code"):
        val = meta.get(key)
        if val:
            return str(val)
    return hit.hit_type


def hit_uid_fields(hit: SearchHit) -> dict[str, str]:
    fields: dict[str, str] = {}
    mapping = {
        "document_uid": hit.document_uid,
        "content_uid": hit.content_uid,
        "chunk_uid": hit.chunk_uid,
        "evidence_uid": hit.evidence_uid,
        "project_uid": hit.project_uid,
        "curated_uid": hit.curated_uid,
    }
    for key, val in mapping.items():
        if val:
            fields[key] = val
    return fields


def search_hit_row(hit: SearchHit) -> dict[str, Any]:
    return {
        "hit_type": hit.hit_type,
        "title": hit_display_name(hit),
        "snippet": hit.snippet,
        "relevance_score": round(hit.relevance_score, 4),
        **hit_uid_fields(hit),
    }
