from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import AppConfig
from app.schemas.search import SearchQuery, SearchResponse
from app.services.search_service import SearchService


def search_kb(
    config: AppConfig,
    *,
    query: str,
    scope: str = "all",
    project_code: str | None = None,
    content_uid: str | None = None,
    document_uid: str | None = None,
    limit: int = 20,
    offset: int = 0,
    session_factory: sessionmaker[Session] | None = None,
) -> SearchResponse:
    """Delegate keyword search to SearchService; no UI-layer FULLTEXT SQL."""
    sq = SearchQuery.validate_and_build(
        text=query,
        scope=scope,
        project_code=project_code,
        content_uid=content_uid,
        document_uid=document_uid,
        limit=limit,
        offset=offset,
    )
    service = SearchService(config, session_factory=session_factory)
    return service.search(sq)
