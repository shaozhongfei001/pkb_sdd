from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from app.cli.main import app
from app.core.config import AppConfig, MysqlConfig, RawConfig, StorageConfig
from app.models.document import KbDocument
from app.models.evidence import KbDocumentChunk, KbEvidence
from app.models.project import KbCuratedAsset, KbProject, KbProjectDocument
from app.schemas.search import SearchQuery
from app.services.search_service import (
    REPORT_TYPE,
    SCHEMA_VERSION,
    SearchService,
    _assert_select_only,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_META = PROJECT_ROOT / "backend/tests/fixtures/search/chinese_evidence.fixture.json"

cli_runner = CliRunner()


def _test_config(workspace_root: Path) -> AppConfig:
    return AppConfig(
        pipeline_version="v1.1",
        storage=StorageConfig(
            source_registry_root=workspace_root / "source_registry",
            raw_vault_root=workspace_root / "raw_vault",
            parsed_root=workspace_root / "parsed",
            curated_root=workspace_root / "curated",
            quarantine_root=workspace_root / "quarantine",
            reports_root=workspace_root / "reports",
        ),
        mysql=MysqlConfig(
            host="127.0.0.1",
            port=3306,
            database="personal_kb",
            username="personal_kb",
            password="test",
            charset="utf8mb4",
        ),
        raw=RawConfig(
            original_files_readonly=True,
            copy_unique_content_to_vault=True,
        ),
    )


def _stmt_text(stmt) -> str:
    try:
        return str(stmt.compile(compile_kwargs={"literal_binds": True}))
    except Exception:
        return str(stmt)


def _matches_fulltext(field_value: str | None, query: str) -> bool:
    if not field_value:
        return False
    lowered = field_value.lower()
    tokens = [part for part in re.split(r"\s+", query.strip()) if part]
    if not tokens:
        return False
    return any(token.lower() in lowered for token in tokens)


def _relevance_score(field_value: str | None, query: str) -> float:
    if not _matches_fulltext(field_value, query):
        return 0.0
    return 1.0 + len(query) / 100.0


class _FakeSession:
    def __init__(
        self,
        *,
        documents: dict[str, KbDocument],
        chunks: dict[str, KbDocumentChunk],
        evidence: dict[str, KbEvidence],
        projects: dict[str, KbProject],
        project_documents: list[KbProjectDocument],
        curated_assets: dict[str, KbCuratedAsset],
    ) -> None:
        self.documents = documents
        self.chunks = chunks
        self.evidence = evidence
        self.projects = projects
        self.project_documents = project_documents
        self.curated_assets = curated_assets
        self.executed_sql: list[str] = []
        self.executed_writes = 0

    def execute(self, stmt, params: dict | None = None):
        sql = _stmt_text(stmt)
        self.executed_sql.append(sql)
        if re.search(r"\b(INSERT|UPDATE|DELETE|REPLACE)\b", sql, re.IGNORECASE):
            self.executed_writes += 1
        params = dict(params or {})
        if hasattr(stmt, "compile"):
            try:
                compiled = stmt.compile()
                if compiled.params:
                    params = {**compiled.params, **params}
            except Exception:
                pass

        if "kb_project_document" in sql and "document_uid" in sql.lower():
            project_uid = params.get("project_uid")
            rows = [
                (row.document_uid,)
                for row in self.project_documents
                if row.project_uid == project_uid
            ]
            return _Result(rows)

        return self._run_search(sql, params)

    def scalar(self, stmt, params: dict | None = None):
        sql = _stmt_text(stmt)
        self.executed_sql.append(sql)
        params = dict(params or {})
        if hasattr(stmt, "compile"):
            try:
                compiled = stmt.compile()
                if compiled.params:
                    params = {**compiled.params, **params}
            except Exception:
                pass

        if "project_code" in sql and "kb_project" in sql and "COUNT" not in sql.upper():
            code = params.get("project_code")
            for project in self.projects.values():
                if project.project_code == code:
                    return project.project_uid
            return None

        if "COUNT" in sql.upper():
            result = self._run_search(sql, params)
            rows = result.fetchall()
            return rows[0][0] if rows else 0

        return None

    def _run_search(self, sql: str, params: dict) -> _Result:
        is_count = "COUNT(*)" in sql.upper()
        query_text = str(params.get("q", ""))
        limit = int(params.get("limit", 100))
        offset = int(params.get("offset", 0))
        if is_count:
            limit = 10_000
            offset = 0
        allowed_docs = params.get("allowed_document_uids")
        content_uid = params.get("content_uid")
        document_uid = params.get("document_uid")
        project_code = params.get("project_code")
        filter_project_uid = params.get("filter_project_uid")

        rows: list[tuple] = []

        if "kb_document_chunk" in sql:
            for chunk in self.chunks.values():
                if allowed_docs is not None and chunk.document_uid not in allowed_docs:
                    continue
                if content_uid and chunk.content_uid != content_uid:
                    continue
                if document_uid and chunk.document_uid != document_uid:
                    continue
                if not _matches_fulltext(chunk.content, query_text):
                    continue
                doc = self.documents.get(chunk.document_uid)
                score = _relevance_score(chunk.content, query_text)
                rows.append(
                    (
                        chunk.chunk_uid,
                        chunk.document_uid,
                        chunk.content_uid,
                        chunk.content,
                        chunk.heading_path,
                        chunk.page_no,
                        score,
                        doc.title if doc else None,
                        doc.parser_profile if doc else None,
                    )
                )
            rows.sort(key=lambda r: (-r[6], r[0]))
            if is_count:
                return _Result([(len(rows),)])
            return _Result(rows[offset : offset + limit])

        if "kb_evidence e" in sql:
            for ev in self.evidence.values():
                if allowed_docs is not None and ev.document_uid not in allowed_docs:
                    continue
                if content_uid and ev.content_uid != content_uid:
                    continue
                if document_uid and ev.document_uid != document_uid:
                    continue
                matched = (
                    _matches_fulltext(ev.quote_text, query_text)
                    or _matches_fulltext(ev.normalized_text, query_text)
                )
                if not matched:
                    continue
                doc = self.documents.get(ev.document_uid)
                field = ev.quote_text or ev.normalized_text or ""
                score = _relevance_score(field, query_text)
                rows.append(
                    (
                        ev.evidence_uid,
                        ev.document_uid,
                        ev.content_uid,
                        ev.chunk_uid,
                        ev.quote_text,
                        ev.normalized_text,
                        ev.page_no,
                        ev.heading_path,
                        score,
                        doc.title if doc else None,
                        doc.parser_profile if doc else None,
                    )
                )
            rows.sort(key=lambda r: (-r[8], r[0]))
            if is_count:
                return _Result([(len(rows),)])
            return _Result(rows[offset : offset + limit])

        if "kb_project p" in sql:
            for project in self.projects.values():
                if project_code and project.project_code != project_code:
                    continue
                combined = f"{project.project_name} {project.description or ''}"
                if not _matches_fulltext(combined, query_text):
                    continue
                score = _relevance_score(combined, query_text)
                rows.append(
                    (
                        project.project_uid,
                        project.project_code,
                        project.project_name,
                        project.description,
                        score,
                    )
                )
            rows.sort(key=lambda r: (-r[4], r[0]))
            if is_count:
                return _Result([(len(rows),)])
            return _Result(rows[offset : offset + limit])

        if "kb_curated_asset ca" in sql:
            for asset in self.curated_assets.values():
                if filter_project_uid and asset.project_uid != filter_project_uid:
                    continue
                if not _matches_fulltext(asset.asset_title, query_text):
                    continue
                score = _relevance_score(asset.asset_title, query_text)
                rows.append(
                    (
                        asset.curated_uid,
                        asset.project_uid,
                        asset.asset_type,
                        asset.asset_title,
                        score,
                    )
                )
            rows.sort(key=lambda r: (-r[4], r[0]))
            if is_count:
                return _Result([(len(rows),)])
            return _Result(rows[offset : offset + limit])

        if "FROM kb_document d" in sql and "kb_document_chunk" not in sql and "kb_evidence" not in sql:
            for doc in self.documents.values():
                if allowed_docs is not None and doc.document_uid not in allowed_docs:
                    continue
                if content_uid and doc.content_uid != content_uid:
                    continue
                if document_uid and doc.document_uid != document_uid:
                    continue
                if not _matches_fulltext(doc.title, query_text):
                    continue
                score = _relevance_score(doc.title, query_text)
                rows.append((doc.document_uid, doc.content_uid, doc.title, score))
            rows.sort(key=lambda r: (-r[3], r[0]))
            if is_count:
                return _Result([(len(rows),)])
            return _Result(rows[offset : offset + limit])

        return _Result([])


class _Result:
    def __init__(self, rows: list[tuple]) -> None:
        self._rows = rows

    def fetchall(self) -> list[tuple]:
        return self._rows


class _FakeSessionFactory:
    def __init__(self, session: _FakeSession) -> None:
        self.session = session
        self.sessions: list[_FakeSession] = []

    def __call__(self):
        return self

    def __enter__(self) -> _FakeSession:
        self.sessions.append(self.session)
        return self.session

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def _seed_data() -> dict[str, Any]:
    content_a = "a" * 64
    content_b = "b" * 64
    doc_001 = KbDocument(
        id=1,
        document_uid="doc_001",
        content_uid=content_a,
        source_sha256=content_a,
        title="银行信贷政策文档",
        document_type="pdf",
        parser_name="markitdown",
        parser_version="1.0",
        parser_profile="default_v1",
        pipeline_version="v1.1",
        markdown_path=None,
        json_path=None,
        manifest_path=None,
        quality_path=None,
        output_dir=None,
        page_count=1,
        slide_count=None,
        table_count=None,
        image_count=None,
        heading_count=None,
        text_length=100,
        parse_status="SUCCESS",
        quality_status=None,
        quality_score=None,
        metadata_json=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    doc_002 = KbDocument(
        id=2,
        document_uid="doc_002",
        content_uid=content_b,
        source_sha256=content_b,
        title="无关标题",
        document_type="pdf",
        parser_name="markitdown",
        parser_version="1.0",
        parser_profile="default_v1",
        pipeline_version="v1.1",
        markdown_path=None,
        json_path=None,
        manifest_path=None,
        quality_path=None,
        output_dir=None,
        page_count=1,
        slide_count=None,
        table_count=None,
        image_count=None,
        heading_count=None,
        text_length=50,
        parse_status="SUCCESS",
        quality_status=None,
        quality_score=None,
        metadata_json=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    chunk_001 = KbDocumentChunk(
        id=1,
        chunk_uid="chunk_001",
        document_uid="doc_001",
        content_uid=content_a,
        chunk_index=0,
        chunk_type="text",
        chunk_level="section",
        parent_chunk_uid=None,
        heading_path="第一章/背景",
        page_no=3,
        slide_no=None,
        start_offset=0,
        end_offset=50,
        bbox=None,
        content="银行信贷业务经营规范",
        content_hash=None,
        token_count=None,
        char_count=None,
        evidence_ref=None,
        metadata_json=None,
        created_at=datetime.now(),
    )

    ev_001 = KbEvidence(
        id=1,
        evidence_uid="ev_001",
        project_uid="should_not_filter",
        document_uid="doc_001",
        content_uid=content_a,
        chunk_uid="chunk_001",
        evidence_type="section_quote",
        source_file_path=None,
        source_sha256=content_a,
        source_page_start=None,
        source_page_end=None,
        source_char_start=0,
        source_char_end=20,
        page_no=3,
        slide_no=None,
        heading_path="第一章/背景",
        bbox=None,
        quote_text="银行信贷风险管理",
        normalized_text="银行信贷风险",
        source_location=None,
        confidence=None,
        metadata_json=None,
        created_at=datetime.now(),
    )

    proj_demo = KbProject(
        id=1,
        project_uid="proj_demo",
        project_code="DEMO-2024",
        project_name="Demo银行项目",
        client_name=None,
        domain=None,
        project_type=None,
        year_start=2024,
        year_end=None,
        description="信贷领域描述",
        aliases=None,
        keywords=None,
        document_count=1,
        core_document_count=1,
        completeness_score=None,
        has_requirement_doc=0,
        has_solution_doc=0,
        has_design_doc=0,
        has_delivery_doc=0,
        has_acceptance_doc=0,
        has_training_doc=0,
        value_score=None,
        status="ACTIVE",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    proj_other = KbProject(
        id=2,
        project_uid="proj_other",
        project_code="OTHER-001",
        project_name="其他项目",
        client_name=None,
        domain=None,
        project_type=None,
        year_start=None,
        year_end=None,
        description="无关描述",
        aliases=None,
        keywords=None,
        document_count=0,
        core_document_count=0,
        completeness_score=None,
        has_requirement_doc=0,
        has_solution_doc=0,
        has_design_doc=0,
        has_delivery_doc=0,
        has_acceptance_doc=0,
        has_training_doc=0,
        value_score=None,
        status="ACTIVE",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    mapping = KbProjectDocument(
        id=1,
        project_uid="proj_demo",
        document_uid="doc_001",
        content_uid=content_a,
        candidate_project_code=None,
        candidate_confidence=None,
        confirmed_project_code="DEMO-2024",
        confirmed_by=None,
        confirmed_at=None,
        mapping_method="SEED",
        confidence=None,
        is_primary=1,
        created_at=datetime.now(),
    )

    curated_001 = KbCuratedAsset(
        id=1,
        curated_uid="curated_001",
        project_uid="proj_demo",
        asset_type="evidence_index",
        asset_title="Demo信贷资产索引",
        curated_path="curated/DEMO-2024/10_evidence_index.md",
        related_content_uids=[content_a],
        related_document_uids=["doc_001"],
        related_evidence_uids=["ev_001"],
        generation_method="TEMPLATE_RULE",
        generation_status="SUCCESS",
        version_no=1,
        metadata_json=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    return {
        "documents": {"doc_001": doc_001, "doc_002": doc_002},
        "chunks": {"chunk_001": chunk_001},
        "evidence": {"ev_001": ev_001},
        "projects": {"proj_demo": proj_demo, "proj_other": proj_other},
        "project_documents": [mapping],
        "curated_assets": {"curated_001": curated_001},
    }


def _service(workspace: Path, seed: dict[str, Any] | None = None) -> tuple[SearchService, _FakeSessionFactory]:
    seed = seed or _seed_data()
    session = _FakeSession(
        documents=seed["documents"],
        chunks=seed["chunks"],
        evidence=seed["evidence"],
        projects=seed["projects"],
        project_documents=seed["project_documents"],
        curated_assets=seed["curated_assets"],
    )
    factory = _FakeSessionFactory(session)
    config = _test_config(workspace)
    service = SearchService(config, session_factory=factory)
    return service, factory


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "workspace"
    for name in (
        "source_registry",
        "raw_vault",
        "parsed",
        "curated",
        "quarantine",
        "reports",
    ):
        (root / name).mkdir(parents=True)
    return root


def test_document_scope_hit(workspace: Path) -> None:
    service, _ = _service(workspace)
    response = service.search(SearchQuery.validate_and_build(text="银行", scope="document"))
    assert len(response.hits) == 1
    hit = response.hits[0]
    assert hit.hit_type == "document"
    assert hit.matched_field == "title"
    assert hit.document_uid == "doc_001"


def test_chunk_scope_hit(workspace: Path) -> None:
    service, _ = _service(workspace)
    response = service.search(SearchQuery.validate_and_build(text="信贷", scope="chunk"))
    assert len(response.hits) == 1
    assert response.hits[0].hit_type == "chunk"
    assert response.hits[0].chunk_uid == "chunk_001"
    assert response.hits[0].metadata.get("document_title") == "银行信贷政策文档"


def test_evidence_scope_hit(workspace: Path) -> None:
    service, _ = _service(workspace)
    response = service.search(SearchQuery.validate_and_build(text="风险管理", scope="evidence"))
    assert len(response.hits) == 1
    assert response.hits[0].hit_type == "evidence"
    assert response.hits[0].evidence_uid == "ev_001"
    assert response.hits[0].matched_field == "quote_text"


def test_project_scope_hit(workspace: Path) -> None:
    service, _ = _service(workspace)
    response = service.search(SearchQuery.validate_and_build(text="银行", scope="project"))
    assert len(response.hits) == 1
    assert response.hits[0].project_code == "DEMO-2024"


def test_curated_scope_hit(workspace: Path) -> None:
    service, _ = _service(workspace)
    response = service.search(SearchQuery.validate_and_build(text="信贷", scope="curated"))
    assert len(response.hits) == 1
    assert response.hits[0].curated_uid == "curated_001"
    assert response.hits[0].metadata.get("asset_type") == "evidence_index"


def test_scope_all_merge_and_sort(workspace: Path) -> None:
    service, _ = _service(workspace)
    response = service.search(SearchQuery.validate_and_build(text="银行", scope="all", limit=10))
    assert response.total_count >= 4
    assert len(response.hits) >= 4
    hit_types = {hit.hit_type for hit in response.hits}
    assert "document" in hit_types
    assert "chunk" in hit_types
    assert "evidence" in hit_types
    assert "project" in hit_types
    scores = [hit.relevance_score for hit in response.hits]
    assert scores == sorted(scores, reverse=True)


def test_empty_query_rejected(workspace: Path) -> None:
    service, _ = _service(workspace)
    with pytest.raises(Exception) as exc:
        SearchQuery.validate_and_build(text="   ", scope="all")
    assert "SEARCH_EMPTY_QUERY" in str(exc.value.error_code)


def test_no_matches_empty_exit_ok(workspace: Path) -> None:
    service, _ = _service(workspace)
    response = service.search(SearchQuery.validate_and_build(text="不存在的关键词", scope="all"))
    assert response.total_count == 0
    assert response.hits == []


def test_limit_offset(workspace: Path) -> None:
    service, _ = _service(workspace)
    full = service.search(SearchQuery.validate_and_build(text="银行", scope="all", limit=100))
    page = service.search(SearchQuery.validate_and_build(text="银行", scope="all", limit=2, offset=2))
    assert len(page.hits) == 2
    assert page.hits[0] == full.hits[2]


def test_project_code_filter_via_mapping(workspace: Path) -> None:
    service, factory = _service(workspace)
    response = service.search(
        SearchQuery.validate_and_build(
            text="银行",
            scope="document",
            project_code="DEMO-2024",
        )
    )
    assert len(response.hits) == 1
    assert response.hits[0].document_uid == "doc_001"
    sql_joined = "\n".join(factory.session.executed_sql)
    assert "kb_project_document" in sql_joined
    assert "kb_evidence" not in sql_joined


def test_project_code_excludes_unmapped_document(workspace: Path) -> None:
    service, _ = _service(workspace)
    response = service.search(
        SearchQuery.validate_and_build(
            text="无关",
            scope="document",
            project_code="DEMO-2024",
        )
    )
    assert response.total_count == 0


def test_unknown_project_code_raises(workspace: Path) -> None:
    service, _ = _service(workspace)
    with pytest.raises(Exception) as exc:
        service.search(
            SearchQuery.validate_and_build(
                text="银行",
                scope="all",
                project_code="UNKNOWN",
            )
        )
    assert exc.value.error_code == "SEARCH_PROJECT_NOT_FOUND"


def test_content_uid_and_document_uid_filters(workspace: Path) -> None:
    seed = _seed_data()
    service, _ = _service(workspace, seed)
    content_a = seed["documents"]["doc_001"].content_uid
    response = service.search(
        SearchQuery.validate_and_build(
            text="银行",
            scope="chunk",
            content_uid=content_a,
            document_uid="doc_001",
        )
    )
    assert len(response.hits) == 1
    wrong = service.search(
        SearchQuery.validate_and_build(
            text="银行",
            scope="chunk",
            document_uid="doc_002",
        )
    )
    assert wrong.total_count == 0


def test_chinese_query_utf8(workspace: Path) -> None:
    meta = json.loads(FIXTURE_META.read_text(encoding="utf-8"))
    service, _ = _service(workspace)
    for sample in meta["sample_queries"]:
        response = service.search(SearchQuery.validate_and_build(text=sample, scope="all"))
        assert isinstance(response.total_count, int)


def test_json_output_shape(workspace: Path) -> None:
    from app.services.search_service import build_success_payload

    service, _ = _service(workspace)
    config = _test_config(workspace)
    response = service.search(SearchQuery.validate_and_build(text="银行", scope="document"))
    payload = build_success_payload(config, response, "2026-01-01T00:00:00Z")
    assert payload["report_type"] == REPORT_TYPE
    assert payload["schema_version"] == SCHEMA_VERSION
    assert "summary" in payload
    assert payload["summary"]["total_count"] == response.total_count
    assert isinstance(payload["hits"], list)


def test_select_only_guard_blocks_dml() -> None:
    _assert_select_only("SELECT 1")
    with pytest.raises(RuntimeError, match="blocked"):
        _assert_select_only("INSERT INTO kb_evidence VALUES (1)")
    with pytest.raises(RuntimeError, match="blocked"):
        _assert_select_only("UPDATE kb_document SET title='x'")


def test_no_dml_in_executed_sql(workspace: Path) -> None:
    service, factory = _service(workspace)
    service.search(SearchQuery.validate_and_build(text="银行", scope="all"))
    for sql in factory.session.executed_sql:
        assert not re.search(r"\b(INSERT|UPDATE|DELETE|REPLACE)\b", sql, re.IGNORECASE)
    assert factory.session.executed_writes == 0


def test_no_raw_vault_or_parsed_reads(workspace: Path) -> None:
    service, _ = _service(workspace)
    with patch("builtins.open", side_effect=AssertionError("filesystem read blocked")):
        service.search(SearchQuery.validate_and_build(text="银行", scope="all"))


def test_no_curated_filesystem_reads(workspace: Path) -> None:
    service, _ = _service(workspace)
    with patch("pathlib.Path.read_text", side_effect=AssertionError("curated read blocked")):
        service.search(SearchQuery.validate_and_build(text="信贷", scope="curated"))


def test_no_parser_subprocess(workspace: Path) -> None:
    service, _ = _service(workspace)
    with patch("subprocess.run", side_effect=AssertionError("subprocess blocked")):
        service.search(SearchQuery.validate_and_build(text="银行", scope="all"))


def test_no_llm_or_embedding_imports(workspace: Path) -> None:
    service, _ = _service(workspace)
    with patch.dict("sys.modules", {"openai": MagicMock()}):
        service.search(SearchQuery.validate_and_build(text="银行", scope="all"))


def test_cli_smoke_json(workspace: Path) -> None:
    config_path = workspace / "app.yaml"
    config_path.write_text("placeholder", encoding="utf-8")
    config = _test_config(workspace)

    with patch("app.cli.main.load_config", return_value=config), patch(
        "app.cli.main.SearchService"
    ) as service_cls:
        mock_service = MagicMock()
        mock_service.search.return_value = MagicMock(
            query=SearchQuery.validate_and_build(text="测试", scope="all"),
            hits=[],
            total_count=0,
            returned_count=0,
            scopes_executed=list(("document", "chunk", "evidence", "project", "curated")),
            duration_ms=1,
        )
        service_cls.return_value = mock_service

        result = cli_runner.invoke(
            app,
            [
                "search-kb",
                "--config",
                str(config_path),
                "--query",
                "测试",
                "--scope",
                "all",
                "--format",
                "json",
            ],
        )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["report_type"] == REPORT_TYPE


def test_cli_empty_query_exit_1(workspace: Path) -> None:
    config_path = workspace / "app.yaml"
    config_path.write_text("placeholder", encoding="utf-8")
    config = _test_config(workspace)

    with patch("app.cli.main.load_config", return_value=config):
        result = cli_runner.invoke(
            app,
            [
                "search-kb",
                "--config",
                str(config_path),
                "--query",
                "",
                "--format",
                "json",
            ],
        )

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["error_code"] == "SEARCH_EMPTY_QUERY"


def test_cli_unknown_project_exit_1(workspace: Path) -> None:
    config_path = workspace / "app.yaml"
    config_path.write_text("placeholder", encoding="utf-8")
    config = _test_config(workspace)
    service, _ = _service(workspace)

    with patch("app.cli.main.load_config", return_value=config), patch(
        "app.cli.main.SearchService", return_value=service
    ):
        result = cli_runner.invoke(
            app,
            [
                "search-kb",
                "--config",
                str(config_path),
                "--query",
                "银行",
                "--project-code",
                "UNKNOWN",
                "--format",
                "json",
            ],
        )

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["error_code"] == "SEARCH_PROJECT_NOT_FOUND"


def test_cli_output_file(workspace: Path) -> None:
    config_path = workspace / "app.yaml"
    config_path.write_text("placeholder", encoding="utf-8")
    config = _test_config(workspace)
    service, _ = _service(workspace)
    out_path = workspace / "reports" / "search_results.json"

    with patch("app.cli.main.load_config", return_value=config), patch(
        "app.cli.main.SearchService", return_value=service
    ):
        result = cli_runner.invoke(
            app,
            [
                "search-kb",
                "--config",
                str(config_path),
                "--query",
                "银行",
                "--scope",
                "document",
                "--output",
                str(out_path),
            ],
        )

    assert result.exit_code == 0
    assert out_path.is_file()
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["total_count"] >= 1


def test_cli_help_documents_contract() -> None:
    result = cli_runner.invoke(app, ["search-kb", "--help"])
    assert result.exit_code == 0
    assert "ngram_token_size=2" in result.stdout
    assert "kb_project_document" in result.stdout
    assert "raw_vault" in result.stdout
