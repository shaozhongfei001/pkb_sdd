from __future__ import annotations

import logging
import re
import time
from dataclasses import asdict
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import AppConfig
from app.core.database import create_db_engine, create_session_factory
from app.schemas.search import (
    HIT_TYPE_RANK,
    SCOPE_ORDER,
    SearchHit,
    SearchProjectNotFoundError,
    SearchQuery,
    SearchResponse,
    SearchValidationError,
)

logger = logging.getLogger(__name__)

REPORT_TYPE = "search_results"
ERROR_REPORT_TYPE = "search_error"
SCHEMA_VERSION = "1.0"
SNIPPET_MAX = 200

_DML_DENYLIST = re.compile(
    r"\b(INSERT|UPDATE|DELETE|REPLACE|TRUNCATE|CREATE|ALTER|DROP)\b",
    re.IGNORECASE,
)


def _assert_select_only(sql: str) -> None:
    normalized = sql.strip().upper()
    if not normalized.startswith("SELECT"):
        raise RuntimeError(f"Non-SELECT statement blocked: {sql[:120]}")
    if _DML_DENYLIST.search(sql):
        raise RuntimeError(f"DML/DDL blocked in search SQL: {sql[:120]}")


def _make_snippet(source: str | None) -> str:
    if not source:
        return ""
    if len(source) <= SNIPPET_MAX:
        return source
    return source[: SNIPPET_MAX - 1] + "…"


def _hit_sort_key(hit: SearchHit) -> tuple[float, int, str]:
    uid = (
        hit.evidence_uid
        or hit.chunk_uid
        or hit.document_uid
        or hit.curated_uid
        or hit.project_uid
        or ""
    )
    return (-hit.relevance_score, HIT_TYPE_RANK.get(hit.hit_type, 99), uid)


class SearchService:
    def __init__(
        self,
        config: AppConfig,
        session_factory: sessionmaker[Session] | None = None,
    ) -> None:
        self.config = config
        if session_factory is None:
            engine = create_db_engine(config)
            session_factory = create_session_factory(engine)
        self._session_factory = session_factory

    def search(self, query: SearchQuery) -> SearchResponse:
        start = time.perf_counter()
        with self._session_factory() as session:
            project_uid: str | None = None
            allowed_document_uids: list[str] | None = None

            if query.project_code:
                project_uid, allowed_document_uids = self._resolve_project_filter(
                    session, query.project_code
                )

            if query.scope == "all":
                hits, total_count, scopes_executed = self._search_all_scopes(
                    session,
                    query,
                    project_uid=project_uid,
                    allowed_document_uids=allowed_document_uids,
                )
            else:
                scope_hits, scope_total = self._search_scope(
                    session,
                    query.scope,
                    query,
                    project_uid=project_uid,
                    allowed_document_uids=allowed_document_uids,
                    limit=query.limit,
                    offset=query.offset,
                )
                hits = scope_hits
                total_count = scope_total
                scopes_executed = [query.scope]

            duration_ms = int((time.perf_counter() - start) * 1000)
            return SearchResponse(
                query=query,
                hits=hits,
                total_count=total_count,
                returned_count=len(hits),
                scopes_executed=scopes_executed,
                duration_ms=duration_ms,
            )

    def _resolve_project_filter(
        self, session: Session, project_code: str
    ) -> tuple[str, list[str]]:
        project_uid = session.scalar(
            text(
                "SELECT project_uid FROM kb_project WHERE project_code = :project_code"
            ).bindparams(project_code=project_code)
        )
        if project_uid is None:
            raise SearchProjectNotFoundError(
                f"project_code not found: {project_code}",
            )

        rows = session.execute(
            text(
                "SELECT document_uid FROM kb_project_document WHERE project_uid = :project_uid"
            ).bindparams(project_uid=project_uid)
        ).fetchall()
        allowed = [row[0] for row in rows]
        return project_uid, allowed

    def _search_all_scopes(
        self,
        session: Session,
        query: SearchQuery,
        *,
        project_uid: str | None,
        allowed_document_uids: list[str] | None,
    ) -> tuple[list[SearchHit], int, list[str]]:
        merged: list[SearchHit] = []
        total_count = 0
        fetch_cap = query.limit + query.offset

        for scope in SCOPE_ORDER:
            if self._scope_zero_for_project(scope, allowed_document_uids):
                continue

            scope_hits, scope_total = self._search_scope(
                session,
                scope,
                query,
                project_uid=project_uid,
                allowed_document_uids=allowed_document_uids,
                limit=fetch_cap,
                offset=0,
            )
            merged.extend(scope_hits)
            total_count += scope_total

        merged.sort(key=_hit_sort_key)
        page_hits = merged[query.offset : query.offset + query.limit]
        return page_hits, total_count, list(SCOPE_ORDER)

    def _scope_zero_for_project(
        self, scope: str, allowed_document_uids: list[str] | None
    ) -> bool:
        if allowed_document_uids is None:
            return False
        return scope in {"document", "chunk", "evidence"} and not allowed_document_uids

    def _search_scope(
        self,
        session: Session,
        scope: str,
        query: SearchQuery,
        *,
        project_uid: str | None,
        allowed_document_uids: list[str] | None,
        limit: int,
        offset: int,
    ) -> tuple[list[SearchHit], int]:
        if scope == "document":
            return self._search_document(
                session,
                query,
                allowed_document_uids=allowed_document_uids,
                limit=limit,
                offset=offset,
            )
        if scope == "chunk":
            return self._search_chunk(
                session,
                query,
                allowed_document_uids=allowed_document_uids,
                limit=limit,
                offset=offset,
            )
        if scope == "evidence":
            return self._search_evidence(
                session,
                query,
                allowed_document_uids=allowed_document_uids,
                limit=limit,
                offset=offset,
            )
        if scope == "project":
            return self._search_project(
                session,
                query,
                project_code=query.project_code,
                limit=limit,
                offset=offset,
            )
        if scope == "curated":
            return self._search_curated(
                session,
                query,
                project_uid=project_uid,
                limit=limit,
                offset=offset,
            )
        raise SearchValidationError(f"invalid scope: {scope}", "SEARCH_INVALID_SCOPE")

    def _execute_select(
        self, session: Session, sql: str, params: dict[str, Any]
    ) -> list[Any]:
        _assert_select_only(sql)
        stmt = text(sql)
        for key, value in params.items():
            if isinstance(value, list):
                stmt = stmt.bindparams(bindparam(key, expanding=True))
        result = session.execute(stmt, params)
        return list(result.fetchall())

    def _count_select(
        self, session: Session, sql: str, params: dict[str, Any]
    ) -> int:
        _assert_select_only(sql)
        stmt = text(sql)
        for key, value in params.items():
            if isinstance(value, list):
                stmt = stmt.bindparams(bindparam(key, expanding=True))
        count = session.scalar(stmt, params)
        return int(count or 0)

    def _document_filters(
        self,
        query: SearchQuery,
        allowed_document_uids: list[str] | None,
        alias: str = "d",
    ) -> tuple[str, dict[str, Any]]:
        clauses: list[str] = []
        params: dict[str, Any] = {"q": query.text}

        if query.content_uid:
            clauses.append(f"{alias}.content_uid = :content_uid")
            params["content_uid"] = query.content_uid
        if query.document_uid:
            clauses.append(f"{alias}.document_uid = :document_uid")
            params["document_uid"] = query.document_uid
        if allowed_document_uids is not None:
            clauses.append(f"{alias}.document_uid IN :allowed_document_uids")
            params["allowed_document_uids"] = allowed_document_uids

        extra = ""
        if clauses:
            extra = " AND " + " AND ".join(clauses)
        return extra, params

    def _search_document(
        self,
        session: Session,
        query: SearchQuery,
        *,
        allowed_document_uids: list[str] | None,
        limit: int,
        offset: int,
    ) -> tuple[list[SearchHit], int]:
        if self._scope_zero_for_project("document", allowed_document_uids):
            return [], 0

        extra, params = self._document_filters(query, allowed_document_uids)
        match_where = (
            "MATCH(d.title) AGAINST (:q IN NATURAL LANGUAGE MODE)"
        )

        count_sql = (
            f"SELECT COUNT(*) FROM kb_document d "
            f"WHERE {match_where}{extra}"
        )
        total = self._count_select(session, count_sql, params)

        select_sql = (
            f"SELECT d.document_uid, d.content_uid, d.title, "
            f"MATCH(d.title) AGAINST (:q IN NATURAL LANGUAGE MODE) AS relevance_score "
            f"FROM kb_document d "
            f"WHERE {match_where}{extra} "
            f"ORDER BY relevance_score DESC, d.document_uid ASC "
            f"LIMIT :limit OFFSET :offset"
        )
        select_params = dict(params)
        select_params["limit"] = limit
        select_params["offset"] = offset
        rows = self._execute_select(session, select_sql, select_params)

        hits = [
            SearchHit(
                hit_type="document",
                matched_field="title",
                snippet=_make_snippet(row[2]),
                relevance_score=float(row[3]),
                document_uid=row[0],
                content_uid=row[1],
            )
            for row in rows
        ]
        return hits, total

    def _search_chunk(
        self,
        session: Session,
        query: SearchQuery,
        *,
        allowed_document_uids: list[str] | None,
        limit: int,
        offset: int,
    ) -> tuple[list[SearchHit], int]:
        if self._scope_zero_for_project("chunk", allowed_document_uids):
            return [], 0

        extra, params = self._document_filters(
            query, allowed_document_uids, alias="c"
        )
        match_where = "MATCH(c.content) AGAINST (:q IN NATURAL LANGUAGE MODE)"

        count_sql = (
            f"SELECT COUNT(*) FROM kb_document_chunk c "
            f"WHERE {match_where}{extra}"
        )
        total = self._count_select(session, count_sql, params)

        select_sql = (
            f"SELECT c.chunk_uid, c.document_uid, c.content_uid, c.content, "
            f"c.heading_path, c.page_no, "
            f"MATCH(c.content) AGAINST (:q IN NATURAL LANGUAGE MODE) AS relevance_score, "
            f"d.title, d.parser_profile "
            f"FROM kb_document_chunk c "
            f"LEFT JOIN kb_document d ON d.document_uid = c.document_uid "
            f"WHERE {match_where}{extra} "
            f"ORDER BY relevance_score DESC, c.chunk_uid ASC "
            f"LIMIT :limit OFFSET :offset"
        )
        select_params = dict(params)
        select_params["limit"] = limit
        select_params["offset"] = offset
        rows = self._execute_select(session, select_sql, select_params)

        hits = []
        for row in rows:
            metadata: dict[str, Any] = {}
            if row[4]:
                metadata["heading_path"] = row[4]
            if row[5] is not None:
                metadata["page_no"] = row[5]
            if row[7]:
                metadata["document_title"] = row[7]
            if row[8]:
                metadata["parser_profile"] = row[8]
            hits.append(
                SearchHit(
                    hit_type="chunk",
                    matched_field="content",
                    snippet=_make_snippet(row[3]),
                    relevance_score=float(row[6]),
                    chunk_uid=row[0],
                    document_uid=row[1],
                    content_uid=row[2],
                    metadata=metadata,
                )
            )
        return hits, total

    def _search_evidence(
        self,
        session: Session,
        query: SearchQuery,
        *,
        allowed_document_uids: list[str] | None,
        limit: int,
        offset: int,
    ) -> tuple[list[SearchHit], int]:
        if self._scope_zero_for_project("evidence", allowed_document_uids):
            return [], 0

        extra, params = self._document_filters(
            query, allowed_document_uids, alias="e"
        )
        match_expr = "MATCH(e.quote_text, e.normalized_text)"
        match_where = f"{match_expr} AGAINST (:q IN NATURAL LANGUAGE MODE)"

        count_sql = (
            f"SELECT COUNT(*) FROM kb_evidence e "
            f"WHERE {match_where}{extra}"
        )
        total = self._count_select(session, count_sql, params)

        select_sql = (
            f"SELECT e.evidence_uid, e.document_uid, e.content_uid, e.chunk_uid, "
            f"e.quote_text, e.normalized_text, e.page_no, e.heading_path, "
            f"{match_expr} AGAINST (:q IN NATURAL LANGUAGE MODE) AS relevance_score, "
            f"d.title, d.parser_profile "
            f"FROM kb_evidence e "
            f"LEFT JOIN kb_document d ON d.document_uid = e.document_uid "
            f"WHERE {match_where}{extra} "
            f"ORDER BY relevance_score DESC, e.evidence_uid ASC "
            f"LIMIT :limit OFFSET :offset"
        )
        select_params = dict(params)
        select_params["limit"] = limit
        select_params["offset"] = offset
        rows = self._execute_select(session, select_sql, select_params)

        hits = []
        for row in rows:
            quote_text = row[4]
            normalized_text = row[5]
            matched_field = "quote_text"
            snippet_source = quote_text
            if quote_text and query.text.lower() in quote_text.lower():
                matched_field = "quote_text"
                snippet_source = quote_text
            elif normalized_text and query.text.lower() in normalized_text.lower():
                matched_field = "normalized_text"
                snippet_source = normalized_text
            elif normalized_text:
                matched_field = "normalized_text"
                snippet_source = normalized_text

            metadata: dict[str, Any] = {}
            if row[6] is not None:
                metadata["page_no"] = row[6]
            if row[7]:
                metadata["heading_path"] = row[7]
            if row[9]:
                metadata["document_title"] = row[9]
            if row[10]:
                metadata["parser_profile"] = row[10]

            hits.append(
                SearchHit(
                    hit_type="evidence",
                    matched_field=matched_field,
                    snippet=_make_snippet(snippet_source),
                    relevance_score=float(row[8]),
                    evidence_uid=row[0],
                    document_uid=row[1],
                    content_uid=row[2],
                    chunk_uid=row[3],
                    metadata=metadata,
                )
            )
        return hits, total

    def _search_project(
        self,
        session: Session,
        query: SearchQuery,
        *,
        project_code: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[SearchHit], int]:
        clauses: list[str] = []
        params: dict[str, Any] = {"q": query.text}

        if project_code:
            clauses.append("p.project_code = :project_code")
            params["project_code"] = project_code

        extra = ""
        if clauses:
            extra = " AND " + " AND ".join(clauses)

        match_expr = "MATCH(p.project_name, p.description)"
        match_where = f"{match_expr} AGAINST (:q IN NATURAL LANGUAGE MODE)"

        count_sql = (
            f"SELECT COUNT(*) FROM kb_project p "
            f"WHERE {match_where}{extra}"
        )
        total = self._count_select(session, count_sql, params)

        select_sql = (
            f"SELECT p.project_uid, p.project_code, p.project_name, p.description, "
            f"{match_expr} AGAINST (:q IN NATURAL LANGUAGE MODE) AS relevance_score "
            f"FROM kb_project p "
            f"WHERE {match_where}{extra} "
            f"ORDER BY relevance_score DESC, p.project_uid ASC "
            f"LIMIT :limit OFFSET :offset"
        )
        select_params = dict(params)
        select_params["limit"] = limit
        select_params["offset"] = offset
        rows = self._execute_select(session, select_sql, select_params)

        hits = []
        for row in rows:
            snippet_source = row[2] or row[3] or ""
            hits.append(
                SearchHit(
                    hit_type="project",
                    matched_field="project_name",
                    snippet=_make_snippet(snippet_source),
                    relevance_score=float(row[4]),
                    project_uid=row[0],
                    project_code=row[1],
                )
            )
        return hits, total

    def _search_curated(
        self,
        session: Session,
        query: SearchQuery,
        *,
        project_uid: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[SearchHit], int]:
        clauses: list[str] = []
        params: dict[str, Any] = {"q": query.text}

        if project_uid:
            clauses.append("ca.project_uid = :filter_project_uid")
            params["filter_project_uid"] = project_uid

        extra = ""
        if clauses:
            extra = " AND " + " AND ".join(clauses)

        match_where = "MATCH(ca.asset_title) AGAINST (:q IN NATURAL LANGUAGE MODE)"

        count_sql = (
            f"SELECT COUNT(*) FROM kb_curated_asset ca "
            f"WHERE {match_where}{extra}"
        )
        total = self._count_select(session, count_sql, params)

        select_sql = (
            f"SELECT ca.curated_uid, ca.project_uid, ca.asset_type, ca.asset_title, "
            f"MATCH(ca.asset_title) AGAINST (:q IN NATURAL LANGUAGE MODE) AS relevance_score "
            f"FROM kb_curated_asset ca "
            f"WHERE {match_where}{extra} "
            f"ORDER BY relevance_score DESC, ca.curated_uid ASC "
            f"LIMIT :limit OFFSET :offset"
        )
        select_params = dict(params)
        select_params["limit"] = limit
        select_params["offset"] = offset
        rows = self._execute_select(session, select_sql, select_params)

        hits = []
        for row in rows:
            metadata: dict[str, Any] = {"asset_type": row[2]}
            hits.append(
                SearchHit(
                    hit_type="curated",
                    matched_field="asset_title",
                    snippet=_make_snippet(row[3]),
                    relevance_score=float(row[4]),
                    curated_uid=row[0],
                    project_uid=row[1],
                    metadata=metadata,
                )
            )
        return hits, total


def hit_to_dict(hit: SearchHit) -> dict[str, Any]:
    payload = asdict(hit)
    return payload


def build_success_payload(
    config: AppConfig,
    response: SearchResponse,
    generated_at: str,
) -> dict[str, Any]:
    return {
        "report_type": REPORT_TYPE,
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "pipeline_version": config.pipeline_version,
        "query": {
            "text": response.query.text,
            "scope": response.query.scope,
            "project_code": response.query.project_code,
            "content_uid": response.query.content_uid,
            "document_uid": response.query.document_uid,
            "limit": response.query.limit,
            "offset": response.query.offset,
        },
        "summary": {
            "total_count": response.total_count,
            "returned_count": response.returned_count,
            "scopes_executed": response.scopes_executed,
            "duration_ms": response.duration_ms,
        },
        "hits": [hit_to_dict(hit) for hit in response.hits],
        "errors": [],
    }


def build_error_payload(
    config: AppConfig,
    error_code: str,
    message: str,
    query_text: str,
    scope: str,
    project_code: str | None,
    generated_at: str,
) -> dict[str, Any]:
    return {
        "report_type": ERROR_REPORT_TYPE,
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "error_code": error_code,
        "message": message,
        "query": {
            "text": query_text,
            "scope": scope,
            "project_code": project_code,
        },
    }
