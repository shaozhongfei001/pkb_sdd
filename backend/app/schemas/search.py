from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


VALID_SCOPES = frozenset({"all", "document", "chunk", "evidence", "project", "curated"})
SCOPE_ORDER = ("document", "chunk", "evidence", "project", "curated")
HIT_TYPE_RANK = {
    "evidence": 0,
    "chunk": 1,
    "document": 2,
    "curated": 3,
    "project": 4,
}


class SearchValidationError(ValueError):
    error_code: str = "SEARCH_VALIDATION_ERROR"

    def __init__(self, message: str, error_code: str | None = None) -> None:
        super().__init__(message)
        if error_code is not None:
            self.error_code = error_code


class SearchProjectNotFoundError(SearchValidationError):
    error_code = "SEARCH_PROJECT_NOT_FOUND"


@dataclass(frozen=True)
class SearchQuery:
    text: str
    scope: str = "all"
    project_code: str | None = None
    content_uid: str | None = None
    document_uid: str | None = None
    limit: int = 20
    offset: int = 0

    @staticmethod
    def validate_and_build(
        text: str,
        scope: str = "all",
        project_code: str | None = None,
        content_uid: str | None = None,
        document_uid: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> SearchQuery:
        stripped = text.strip()
        if not stripped:
            raise SearchValidationError("query text is empty", "SEARCH_EMPTY_QUERY")

        normalized_scope = scope.strip().lower()
        if normalized_scope not in VALID_SCOPES:
            raise SearchValidationError(
                f"invalid scope: {scope}",
                "SEARCH_INVALID_SCOPE",
            )

        if limit < 1 or limit > 100:
            raise SearchValidationError(
                f"limit must be between 1 and 100: {limit}",
                "SEARCH_INVALID_LIMIT",
            )

        if offset < 0:
            raise SearchValidationError(
                f"offset must be >= 0: {offset}",
                "SEARCH_INVALID_OFFSET",
            )

        return SearchQuery(
            text=stripped,
            scope=normalized_scope,
            project_code=project_code.strip() if project_code else None,
            content_uid=content_uid.strip() if content_uid else None,
            document_uid=document_uid.strip() if document_uid else None,
            limit=limit,
            offset=offset,
        )


@dataclass
class SearchHit:
    hit_type: str
    matched_field: str
    snippet: str
    relevance_score: float
    document_uid: str | None = None
    content_uid: str | None = None
    chunk_uid: str | None = None
    evidence_uid: str | None = None
    project_uid: str | None = None
    project_code: str | None = None
    curated_uid: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResponse:
    query: SearchQuery
    hits: list[SearchHit]
    total_count: int
    returned_count: int
    scopes_executed: list[str]
    duration_ms: int
