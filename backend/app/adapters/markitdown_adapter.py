from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from app.core.parser_routing import RouteType

PARSER_NAME = "markitdown"
PARSER_ADAPTER_VERSION = "005_mvp_v1"

ERROR_PARSER_IMPORT = "PARSER_IMPORT_ERROR"
ERROR_PARSER_RUNTIME = "PARSER_RUNTIME_ERROR"
ERROR_CORRUPTED_DOCUMENT = "CORRUPTED_DOCUMENT"
ERROR_PASSWORD_PROTECTED = "PASSWORD_PROTECTED"


class MarkItDownAdapterError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class AdapterResult:
    text: str
    metadata: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class MarkItDownAdapter:
    @classmethod
    def check_import(cls) -> None:
        try:
            import markitdown  # noqa: F401
        except ImportError as exc:
            raise MarkItDownAdapterError(
                ERROR_PARSER_IMPORT,
                f"Failed to import markitdown: {exc}",
            ) from exc

    def convert(self, *, input_path: Path, route_type: RouteType) -> AdapterResult:
        try:
            from markitdown import MarkItDown
        except ImportError as exc:
            raise MarkItDownAdapterError(
                ERROR_PARSER_IMPORT,
                f"Failed to import markitdown: {exc}",
            ) from exc

        warnings: list[str] = []
        try:
            converter = MarkItDown()
            result = converter.convert(str(input_path))
        except Exception as exc:
            code = _classify_runtime_error(exc)
            raise MarkItDownAdapterError(code, str(exc)) from exc

        text = _extract_text(result)
        metadata = _extract_metadata(result, route_type)
        library_version = _library_version()
        metadata.setdefault("library_version", library_version)
        metadata.setdefault("route_type", route_type.value)

        return AdapterResult(text=text, metadata=metadata, warnings=warnings)


def _extract_text(result: object) -> str:
    text_content = getattr(result, "text_content", None)
    if text_content is None:
        return ""
    return str(text_content)


def _extract_metadata(result: object, route_type: RouteType) -> dict:
    extra: dict = {"route_type": route_type.value}
    title = getattr(result, "title", None)
    if title:
        extra["title"] = title
    return extra


def _library_version() -> str:
    try:
        import markitdown

        return str(getattr(markitdown, "__version__", "unknown"))
    except ImportError:
        return "unknown"


def _classify_runtime_error(exc: Exception) -> str:
    message = str(exc).lower()
    if _looks_password_protected(message):
        return ERROR_PASSWORD_PROTECTED
    if _looks_corrupted(message):
        return ERROR_CORRUPTED_DOCUMENT
    return ERROR_PARSER_RUNTIME


def _looks_password_protected(message: str) -> bool:
    patterns = (
        r"password",
        r"encrypted",
        r"decrypt",
        r"protected",
        r"office open xml",
    )
    return any(re.search(pattern, message) for pattern in patterns)


def _looks_corrupted(message: str) -> bool:
    patterns = (
        r"corrupt",
        r"invalid",
        r"bad zip",
        r"not a zip",
        r"truncated",
        r"cannot open",
        r"damaged",
        r"malformed",
        r"parse error",
        r"unsupported format",
    )
    return any(re.search(pattern, message) for pattern in patterns)
