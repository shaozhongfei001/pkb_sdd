from __future__ import annotations

from enum import Enum
from pathlib import Path

from app.core.file_types import DOCUMENT_EXTENSIONS

ROUTING_RULES_VERSION = "004_mvp_v1"

DECISION_ROUTE = "ROUTE"
DECISION_UNKNOWN = "UNKNOWN"
DECISION_UNSUPPORTED = "UNSUPPORTED"

IMAGE_EXTENSIONS = frozenset(
    {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff", ".webp"}
)
TEXT_EXTENSIONS = frozenset({".txt", ".md", ".markdown", ".csv"})
MARKUP_EXTENSIONS = frozenset({".html", ".htm", ".xml", ".json"})
LEGACY_OFFICE_EXTENSIONS = frozenset({".doc", ".ppt", ".xls"})
OTHER_OFFICE_EXTENSIONS = frozenset({".rtf", ".odt", ".ods", ".odp"})


class RouteType(str, Enum):
    DOCX = "DOCX"
    PPTX = "PPTX"
    XLSX = "XLSX"
    PDF_DIGITAL = "PDF_DIGITAL"
    PDF_SCANNED_OR_IMAGE = "PDF_SCANNED_OR_IMAGE"
    IMAGE = "IMAGE"
    TEXT_OR_MARKDOWN = "TEXT_OR_MARKDOWN"
    UNKNOWN = "UNKNOWN"
    UNSUPPORTED = "UNSUPPORTED"


class FutureParserHint(str, Enum):
    MARKITDOWN_FAMILY = "MARKITDOWN_FAMILY"
    MINERU_FAMILY = "MINERU_FAMILY"
    DIRECT_TEXT = "DIRECT_TEXT"
    NONE = "NONE"


def normalize_file_ext(ext: str | None) -> str | None:
    if ext is None:
        return None
    normalized = ext.strip().lower()
    if not normalized:
        return None
    if not normalized.startswith("."):
        normalized = f".{normalized}"
    return normalized


def ext_from_path(path: str) -> str | None:
    suffix = Path(path).suffix
    if not suffix:
        return None
    return normalize_file_ext(suffix)


def match_route_type(
    *,
    file_ext: str | None,
    mime_type: str | None,
    fallback_ext: str | None = None,
) -> tuple[RouteType, str, str, str, str]:
    normalized_ext = normalize_file_ext(file_ext)
    normalized_fallback = normalize_file_ext(fallback_ext)
    effective_ext = normalized_ext or normalized_fallback

    if effective_ext == ".pdf" and mime_type and mime_type.lower().startswith("image/"):
        reason = (
            f"file_ext .pdf conflicts with mime_type {mime_type}; "
            "cannot classify without reading file content"
        )
        return (
            RouteType.UNKNOWN,
            DECISION_UNKNOWN,
            "ext_mime_conflict",
            FutureParserHint.NONE.value,
            reason,
        )

    if effective_ext == ".docx":
        return _route(
            RouteType.DOCX,
            "ext_docx",
            FutureParserHint.MARKITDOWN_FAMILY,
            "file_ext .docx maps to DOCX",
        )
    if effective_ext == ".pptx":
        return _route(
            RouteType.PPTX,
            "ext_pptx",
            FutureParserHint.MARKITDOWN_FAMILY,
            "file_ext .pptx maps to PPTX",
        )
    if effective_ext == ".xlsx":
        return _route(
            RouteType.XLSX,
            "ext_xlsx",
            FutureParserHint.MARKITDOWN_FAMILY,
            "file_ext .xlsx maps to XLSX",
        )
    if effective_ext == ".pdf":
        return _route(
            RouteType.PDF_DIGITAL,
            "ext_pdf_digital",
            FutureParserHint.MINERU_FAMILY,
            "file_ext .pdf maps to PDF_DIGITAL",
        )
    if effective_ext in IMAGE_EXTENSIONS:
        return _route(
            RouteType.IMAGE,
            "ext_image",
            FutureParserHint.MINERU_FAMILY,
            f"file_ext {effective_ext} maps to IMAGE",
        )
    if effective_ext in TEXT_EXTENSIONS:
        return _route(
            RouteType.TEXT_OR_MARKDOWN,
            "ext_text",
            FutureParserHint.DIRECT_TEXT,
            f"file_ext {effective_ext} maps to TEXT_OR_MARKDOWN",
        )
    if effective_ext in MARKUP_EXTENSIONS:
        return _route(
            RouteType.TEXT_OR_MARKDOWN,
            "ext_markup_json",
            FutureParserHint.DIRECT_TEXT,
            f"file_ext {effective_ext} maps to TEXT_OR_MARKDOWN",
        )
    if effective_ext in LEGACY_OFFICE_EXTENSIONS:
        return _unsupported(
            "ext_legacy_office",
            f"file_ext {effective_ext} is legacy Office; not parsed in Phase 1",
        )
    if effective_ext in OTHER_OFFICE_EXTENSIONS:
        return _unsupported(
            "ext_other_office",
            f"file_ext {effective_ext} is not supported in Phase 1",
        )

    if effective_ext is None:
        source = "file_ext and fallback_ext both missing"
        return _unknown("ext_missing", f"{source}; cannot determine route_type")

    if effective_ext in DOCUMENT_EXTENSIONS:
        return _unknown(
            "ext_unknown",
            f"file_ext {effective_ext} is a document extension without a routing rule",
        )

    return _unknown(
        "ext_unrecognized",
        f"file_ext {effective_ext} is not recognized for parser routing",
    )


def _route(
    route_type: RouteType,
    rule_name: str,
    hint: FutureParserHint,
    reason: str,
) -> tuple[RouteType, str, str, str, str]:
    return route_type, DECISION_ROUTE, rule_name, hint.value, reason


def _unknown(rule_name: str, reason: str) -> tuple[RouteType, str, str, str, str]:
    return RouteType.UNKNOWN, DECISION_UNKNOWN, rule_name, FutureParserHint.NONE.value, reason


def _unsupported(rule_name: str, reason: str) -> tuple[RouteType, str, str, str, str]:
    return (
        RouteType.UNSUPPORTED,
        DECISION_UNSUPPORTED,
        rule_name,
        FutureParserHint.NONE.value,
        reason,
    )
