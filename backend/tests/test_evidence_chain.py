from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.dialects import mysql
from typer.testing import CliRunner

from app.cli.main import app
from app.core.config import AppConfig, MysqlConfig, RawConfig, StorageConfig
from app.core.parsed_paths import build_parsed_artifact_paths, build_parsed_content_dir
from app.models.document import KbDocument
from app.models.evidence import KbDocumentChunk, KbEvidence
from app.models.parse_registry import KbParseResult
from app.services.evidence_chain import (
    REPORT_TYPE,
    EvidenceChainBuildResult,
    EvidenceChainService,
    _chunk_uid,
    _content_hash,
    _evidence_uid,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MARKITDOWN_FIXTURE = PROJECT_ROOT / "backend/tests/fixtures/evidence_chain_markitdown"
MINERU_FIXTURE = PROJECT_ROOT / "backend/tests/fixtures/evidence_chain_mineru"
CHINESE_FIXTURE = PROJECT_ROOT / "backend/tests/fixtures/中文路径/银行项目"

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


class _FakeSession:
    def __init__(
        self,
        *,
        parse_results: list[KbParseResult],
        documents: dict[str, KbDocument] | None = None,
        shared_chunks: dict[str, KbDocumentChunk] | None = None,
        shared_evidence: dict[str, KbEvidence] | None = None,
    ) -> None:
        self.parse_results = parse_results
        self.documents = documents or {}
        self.chunks = shared_chunks if shared_chunks is not None else {}
        self.evidence = shared_evidence if shared_evidence is not None else {}
        self.committed = False
        self.rolled_back = False
        self.executed_writes = 0

    def scalar(self, stmt):
        stmt_text = _stmt_text(stmt)
        if "count(" in stmt_text.lower() and "kb_document_chunk" in stmt_text:
            content_uid = _extract_filter_value(stmt_text, "content_uid")
            if content_uid:
                return sum(
                    1 for item in self.chunks.values() if item.content_uid == content_uid
                )
            return len(self.chunks)
        if "kb_document" in stmt_text:
            for document in self.documents.values():
                if document.content_uid in stmt_text:
                    return document
        if "kb_parse_result" in stmt_text:
            content_uid = _extract_filter_value(stmt_text, "content_uid")
            sha256 = _extract_filter_value(stmt_text, "sha256")
            for result in self.parse_results:
                if content_uid and result.content_uid != content_uid:
                    continue
                if sha256 and result.sha256 != sha256:
                    continue
                return result
        return None

    def scalars(self, stmt):
        stmt_text = _stmt_text(stmt)
        if "kb_parse_result" not in stmt_text:
            return _ScalarResult([])
        matches = list(self.parse_results)
        content_uid = _extract_filter_value(stmt_text, "content_uid")
        if content_uid:
            matches = [item for item in matches if item.content_uid == content_uid]
        sha256 = _extract_filter_value(stmt_text, "sha256")
        if sha256:
            matches = [item for item in matches if item.sha256 == sha256]
        matches = [item for item in matches if item.status in {"SUCCESS", "EMPTY"}]
        limit = _extract_limit(stmt_text)
        if limit is not None:
            matches = matches[:limit]
        deduped: list[KbParseResult] = []
        seen: set[str] = set()
        for item in sorted(matches, key=lambda row: row.id, reverse=True):
            if item.content_uid in seen:
                continue
            seen.add(item.content_uid)
            deduped.append(item)
        return _ScalarResult(deduped)

    def execute(self, stmt) -> None:
        compiled = str(stmt)
        try:
            values = dict(stmt.compile(dialect=mysql.dialect()).params)
        except Exception:
            values = _extract_insert_values(stmt)
        if "kb_document_chunk" in compiled and values.get("chunk_uid"):
            self.executed_writes += 1
            uid = values["chunk_uid"]
            self.chunks[uid] = KbDocumentChunk(
                id=len(self.chunks) + 1,
                chunk_uid=uid,
                document_uid=values.get("document_uid", ""),
                content_uid=values.get("content_uid", ""),
                chunk_index=values.get("chunk_index", 0),
                chunk_type=values.get("chunk_type"),
                chunk_level=values.get("chunk_level"),
                parent_chunk_uid=values.get("parent_chunk_uid"),
                heading_path=values.get("heading_path"),
                page_no=values.get("page_no"),
                slide_no=values.get("slide_no"),
                start_offset=values.get("start_offset"),
                end_offset=values.get("end_offset"),
                bbox=values.get("bbox"),
                content=values.get("content", ""),
                content_hash=values.get("content_hash"),
                token_count=values.get("token_count"),
                char_count=values.get("char_count"),
                evidence_ref=values.get("evidence_ref"),
                metadata_json=values.get("metadata"),
                created_at=datetime.now(),
            )
        if "kb_evidence" in compiled and values.get("evidence_uid"):
            self.executed_writes += 1
            uid = values["evidence_uid"]
            self.evidence[uid] = KbEvidence(
                id=len(self.evidence) + 1,
                evidence_uid=uid,
                project_uid=values.get("project_uid"),
                document_uid=values.get("document_uid", ""),
                content_uid=values.get("content_uid", ""),
                chunk_uid=values.get("chunk_uid"),
                evidence_type=values.get("evidence_type"),
                source_file_path=values.get("source_file_path"),
                source_sha256=values.get("source_sha256"),
                source_page_start=values.get("source_page_start"),
                source_page_end=values.get("source_page_end"),
                source_char_start=values.get("source_char_start"),
                source_char_end=values.get("source_char_end"),
                page_no=values.get("page_no"),
                slide_no=values.get("slide_no"),
                heading_path=values.get("heading_path"),
                bbox=values.get("bbox"),
                quote_text=values.get("quote_text"),
                normalized_text=values.get("normalized_text"),
                source_location=values.get("source_location"),
                confidence=values.get("confidence"),
                metadata_json=values.get("metadata"),
                created_at=datetime.now(),
            )

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def __enter__(self) -> _FakeSession:
        return self

    def __exit__(self, *args) -> None:
        return None


class _ScalarResult:
    def __init__(self, items: list) -> None:
        self._items = items

    def all(self) -> list:
        return list(self._items)


def _extract_filter_value(stmt_text: str, column: str) -> str | None:
    marker = f"{column} = '"
    if marker not in stmt_text:
        return None
    start = stmt_text.index(marker) + len(marker)
    end = stmt_text.index("'", start)
    return stmt_text[start:end]


def _extract_limit(stmt_text: str) -> int | None:
    upper = stmt_text.upper()
    if " LIMIT " not in upper:
        return None
    fragment = upper.split(" LIMIT ", 1)[1]
    return int(fragment.split()[0])


def _extract_insert_values(stmt) -> dict:
    if hasattr(stmt, "parameters") and isinstance(stmt.parameters, dict):
        return dict(stmt.parameters)
    compiled_params = getattr(stmt, "compiled_parameters", None)
    if isinstance(compiled_params, list) and compiled_params:
        return dict(compiled_params[0])
    return {}


def _session_factory(
    *,
    parse_results: list[KbParseResult],
    documents: dict[str, KbDocument] | None = None,
) -> Callable[[], _FakeSession]:
    sessions: list[_FakeSession] = []
    shared_chunks: dict[str, KbDocumentChunk] = {}
    shared_evidence: dict[str, KbEvidence] = {}

    def factory() -> _FakeSession:
        session = _FakeSession(
            parse_results=parse_results,
            documents=documents,
            shared_chunks=shared_chunks,
            shared_evidence=shared_evidence,
        )
        sessions.append(session)
        return session

    factory.sessions = sessions  # type: ignore[attr-defined]
    factory.shared_chunks = shared_chunks  # type: ignore[attr-defined]
    factory.shared_evidence = shared_evidence  # type: ignore[attr-defined]
    return factory


def _parse_result(
    *,
    sha256: str,
    content_uid: str,
    parser_name: str = "markitdown",
    status: str = "SUCCESS",
    parsed_dir: str | None = None,
    manifest_path: str | None = None,
    text_path: str | None = None,
    metadata_path: str | None = None,
    result_uid: str = "parse_result_test",
) -> KbParseResult:
    return KbParseResult(
        id=1,
        result_uid=result_uid,
        run_uid="parse_run_test",
        content_uid=content_uid,
        sha256=sha256,
        route_type="OFFICE_DOCX",
        decision="PARSED",
        status=status,
        source_vault_path=None,
        parsed_dir=parsed_dir,
        manifest_path=manifest_path,
        metadata_path=metadata_path,
        text_path=text_path,
        output_hash=None,
        output_size_bytes=None,
        error_code=None,
        error_message=None,
        retry_of_result_id=None,
        parser_name=parser_name,
        parser_adapter_version="test-adapter-v1",
        pipeline_version="v1.1",
        metadata_json=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


def _install_parsed_tree(
    workspace: Path,
    *,
    sha256: str,
    content_uid: str,
    fixture_dir: Path,
) -> dict[str, Path]:
    parsed_dir = build_parsed_content_dir(workspace / "parsed", sha256)
    parsed_dir.mkdir(parents=True, exist_ok=True)
    artifacts = build_parsed_artifact_paths(parsed_dir)
    shutil.copy(fixture_dir / "parsed_text.fixture", artifacts["parsed_text"])
    shutil.copy(fixture_dir / "parsed_metadata.fixture", artifacts["parsed_metadata"])
    manifest_template = (fixture_dir / "parse_manifest.fixture").read_text(encoding="utf-8")
    manifest_text = (
        manifest_template.replace("PLACEHOLDER_CONTENT_UID", content_uid)
        .replace("PLACEHOLDER_SHA256", sha256)
        .replace("PLACEHOLDER_PARSED_TEXT", artifacts["parsed_text"].as_posix())
        .replace("PLACEHOLDER_PARSED_METADATA", artifacts["parsed_metadata"].as_posix())
    )
    artifacts["parse_manifest"].write_text(manifest_text, encoding="utf-8")
    return artifacts


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    for name in ("parsed", "raw_vault", "curated", "reports"):
        (tmp_path / name).mkdir()
    return tmp_path


def _service(
    workspace: Path,
    *,
    parse_results: list[KbParseResult],
    documents: dict[str, KbDocument] | None = None,
) -> tuple[EvidenceChainService, Callable]:
    factory = _session_factory(parse_results=parse_results, documents=documents)
    service = EvidenceChainService(_test_config(workspace), session_factory=factory)
    return service, factory


def test_dry_run_zero_db_writes(workspace: Path) -> None:
    sha256 = "a" * 64
    content_uid = sha256
    artifacts = _install_parsed_tree(
        workspace,
        sha256=sha256,
        content_uid=content_uid,
        fixture_dir=MARKITDOWN_FIXTURE,
    )
    parse_result = _parse_result(
        sha256=sha256,
        content_uid=content_uid,
        parsed_dir=artifacts["parsed_dir"].as_posix(),
        manifest_path=artifacts["parse_manifest"].as_posix(),
        text_path=artifacts["parsed_text"].as_posix(),
        metadata_path=artifacts["parsed_metadata"].as_posix(),
    )
    service, factory = _service(workspace, parse_results=[parse_result])

    result = service.build(content_uid=content_uid, dry_run=True)

    assert result.documents_processed == 1
    assert result.chunks_planned > 0
    assert result.chunks_upserted == 0
    assert result.evidence_upserted == 0
    session = factory.sessions[-1]
    assert session.executed_writes == 0
    assert session.committed is False
    assert session.rolled_back is True
    assert len(session.chunks) == 0
    assert len(session.evidence) == 0


def test_repeated_run_idempotent(workspace: Path) -> None:
    sha256 = "b" * 64
    content_uid = sha256
    artifacts = _install_parsed_tree(
        workspace,
        sha256=sha256,
        content_uid=content_uid,
        fixture_dir=MARKITDOWN_FIXTURE,
    )
    parse_result = _parse_result(
        sha256=sha256,
        content_uid=content_uid,
        parsed_dir=artifacts["parsed_dir"].as_posix(),
        manifest_path=artifacts["parse_manifest"].as_posix(),
        text_path=artifacts["parsed_text"].as_posix(),
        metadata_path=artifacts["parsed_metadata"].as_posix(),
    )
    service, factory = _service(workspace, parse_results=[parse_result])

    first = service.build(content_uid=content_uid, force=True)
    second = service.build(content_uid=content_uid, force=True)

    assert first.chunks_upserted > 0
    assert second.chunks_upserted > 0
    session = factory.sessions[-1]
    assert len(session.chunks) == first.chunks_upserted
    assert len(session.evidence) == first.evidence_upserted
    uids_first = set(factory.sessions[0].chunks)
    uids_second = set(session.chunks)
    assert uids_first == uids_second


def test_missing_parsed_artifact_skips_without_repair(workspace: Path) -> None:
    sha256 = "c" * 64
    content_uid = sha256
    parsed_dir = build_parsed_content_dir(workspace / "parsed", sha256)
    parsed_dir.mkdir(parents=True)
    artifacts = build_parsed_artifact_paths(parsed_dir)
    artifacts["parse_manifest"].write_text("{}", encoding="utf-8")
    parse_result = _parse_result(
        sha256=sha256,
        content_uid=content_uid,
        parsed_dir=parsed_dir.as_posix(),
        manifest_path=artifacts["parse_manifest"].as_posix(),
    )
    service, _factory = _service(workspace, parse_results=[parse_result])

    result = service.build(content_uid=content_uid, force=True)

    assert result.documents_processed == 0
    assert len(result.errors) == 1
    assert "missing parsed_text.md" in result.errors[0]


def test_markitdown_section_chunks_without_page_bbox(workspace: Path) -> None:
    sha256 = "d" * 64
    content_uid = sha256
    artifacts = _install_parsed_tree(
        workspace,
        sha256=sha256,
        content_uid=content_uid,
        fixture_dir=MARKITDOWN_FIXTURE,
    )
    parse_result = _parse_result(
        sha256=sha256,
        content_uid=content_uid,
        parsed_dir=artifacts["parsed_dir"].as_posix(),
        manifest_path=artifacts["parse_manifest"].as_posix(),
        text_path=artifacts["parsed_text"].as_posix(),
        metadata_path=artifacts["parsed_metadata"].as_posix(),
    )
    service, factory = _service(workspace, parse_results=[parse_result])

    result = service.build(content_uid=content_uid, force=True)

    assert result.documents_processed == 1
    chunks = list(factory.sessions[-1].chunks.values())
    assert chunks
    assert all(chunk.chunk_level == "section" for chunk in chunks)
    assert all(chunk.page_no is None for chunk in chunks)
    assert all(chunk.bbox is None for chunk in chunks)


def test_mineru_page_bbox_best_effort(workspace: Path) -> None:
    sha256 = "e" * 64
    content_uid = sha256
    artifacts = _install_parsed_tree(
        workspace,
        sha256=sha256,
        content_uid=content_uid,
        fixture_dir=MINERU_FIXTURE,
    )
    parse_result = _parse_result(
        sha256=sha256,
        content_uid=content_uid,
        parser_name="mineru",
        parsed_dir=artifacts["parsed_dir"].as_posix(),
        manifest_path=artifacts["parse_manifest"].as_posix(),
        text_path=artifacts["parsed_text"].as_posix(),
        metadata_path=artifacts["parsed_metadata"].as_posix(),
    )
    service, factory = _service(workspace, parse_results=[parse_result])

    result = service.build(content_uid=content_uid, force=True)

    chunks = list(factory.sessions[-1].chunks.values())
    assert result.documents_processed == 1
    assert len(chunks) == 2
    assert chunks[0].page_no == 1
    assert chunks[0].bbox == {"coordinates": [10.0, 20.0, 100.0, 200.0]}
    assert chunks[1].page_no == 2
    assert chunks[1].bbox is None


def test_does_not_read_raw_vault_binary(workspace: Path, monkeypatch) -> None:
    sha256 = "f" * 64
    content_uid = sha256
    artifacts = _install_parsed_tree(
        workspace,
        sha256=sha256,
        content_uid=content_uid,
        fixture_dir=MARKITDOWN_FIXTURE,
    )
    parse_result = _parse_result(
        sha256=sha256,
        content_uid=content_uid,
        parsed_dir=artifacts["parsed_dir"].as_posix(),
        manifest_path=artifacts["parse_manifest"].as_posix(),
        text_path=artifacts["parsed_text"].as_posix(),
        metadata_path=artifacts["parsed_metadata"].as_posix(),
    )
    service, _factory = _service(workspace, parse_results=[parse_result])

    original_open = Path.open
    opened: list[Path] = []

    def tracking_open(self, *args, **kwargs):
        opened.append(self)
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", tracking_open)

    service.build(content_uid=content_uid, force=True)

    assert not any(path.name == "original.bin" for path in opened)


def test_does_not_call_parser_services(workspace: Path) -> None:
    sha256 = "1" * 64
    content_uid = sha256
    artifacts = _install_parsed_tree(
        workspace,
        sha256=sha256,
        content_uid=content_uid,
        fixture_dir=MARKITDOWN_FIXTURE,
    )
    parse_result = _parse_result(
        sha256=sha256,
        content_uid=content_uid,
        parsed_dir=artifacts["parsed_dir"].as_posix(),
        manifest_path=artifacts["parse_manifest"].as_posix(),
        text_path=artifacts["parsed_text"].as_posix(),
        metadata_path=artifacts["parsed_metadata"].as_posix(),
    )
    service, _factory = _service(workspace, parse_results=[parse_result])

    with patch("app.services.markitdown_parser.MarkItDownParserService") as markitdown_mock, patch(
        "app.services.mineru_pdf_parser.MineruPdfParserService"
    ) as mineru_mock:
        service.build(content_uid=content_uid, force=True)
        markitdown_mock.assert_not_called()
        mineru_mock.assert_not_called()


def test_does_not_write_curated(workspace: Path) -> None:
    sha256 = "2" * 64
    content_uid = sha256
    artifacts = _install_parsed_tree(
        workspace,
        sha256=sha256,
        content_uid=content_uid,
        fixture_dir=MARKITDOWN_FIXTURE,
    )
    parse_result = _parse_result(
        sha256=sha256,
        content_uid=content_uid,
        parsed_dir=artifacts["parsed_dir"].as_posix(),
        manifest_path=artifacts["parse_manifest"].as_posix(),
        text_path=artifacts["parsed_text"].as_posix(),
        metadata_path=artifacts["parsed_metadata"].as_posix(),
    )
    service, _factory = _service(workspace, parse_results=[parse_result])
    curated_before = list((workspace / "curated").rglob("*"))

    service.build(content_uid=content_uid, force=True)

    curated_after = list((workspace / "curated").rglob("*"))
    assert curated_before == curated_after


def test_registry_models_unchanged(workspace: Path) -> None:
    sha256 = "3" * 64
    content_uid = sha256
    artifacts = _install_parsed_tree(
        workspace,
        sha256=sha256,
        content_uid=content_uid,
        fixture_dir=MARKITDOWN_FIXTURE,
    )
    parse_result = _parse_result(
        sha256=sha256,
        content_uid=content_uid,
        parsed_dir=artifacts["parsed_dir"].as_posix(),
        manifest_path=artifacts["parse_manifest"].as_posix(),
        text_path=artifacts["parsed_text"].as_posix(),
        metadata_path=artifacts["parsed_metadata"].as_posix(),
    )
    service, factory = _service(workspace, parse_results=[parse_result])

    service.build(content_uid=content_uid, force=True)

    session = factory.sessions[-1]
    assert len(session.parse_results) == 1
    assert session.parse_results[0].status == "SUCCESS"


def test_parsed_mtime_unchanged(workspace: Path) -> None:
    sha256 = "4" * 64
    content_uid = sha256
    artifacts = _install_parsed_tree(
        workspace,
        sha256=sha256,
        content_uid=content_uid,
        fixture_dir=MARKITDOWN_FIXTURE,
    )
    parse_result = _parse_result(
        sha256=sha256,
        content_uid=content_uid,
        parsed_dir=artifacts["parsed_dir"].as_posix(),
        manifest_path=artifacts["parse_manifest"].as_posix(),
        text_path=artifacts["parsed_text"].as_posix(),
        metadata_path=artifacts["parsed_metadata"].as_posix(),
    )
    service, _factory = _service(workspace, parse_results=[parse_result])
    mtimes = {
        path: path.stat().st_mtime
        for path in (
            artifacts["parsed_text"],
            artifacts["parsed_metadata"],
            artifacts["parse_manifest"],
        )
    }

    service.build(content_uid=content_uid, force=True)

    for path, mtime in mtimes.items():
        assert path.stat().st_mtime == mtime


def test_force_upsert_no_duplicate_rows(workspace: Path) -> None:
    sha256 = "5" * 64
    content_uid = sha256
    artifacts = _install_parsed_tree(
        workspace,
        sha256=sha256,
        content_uid=content_uid,
        fixture_dir=MARKITDOWN_FIXTURE,
    )
    parse_result = _parse_result(
        sha256=sha256,
        content_uid=content_uid,
        parsed_dir=artifacts["parsed_dir"].as_posix(),
        manifest_path=artifacts["parse_manifest"].as_posix(),
        text_path=artifacts["parsed_text"].as_posix(),
        metadata_path=artifacts["parsed_metadata"].as_posix(),
    )
    service, factory = _service(workspace, parse_results=[parse_result])

    service.build(content_uid=content_uid, force=True)
    count_after_first = len(factory.sessions[0].chunks)
    service.build(content_uid=content_uid, force=True)
    count_after_second = len(factory.sessions[-1].chunks)
    assert count_after_first == count_after_second


def test_output_json_report(workspace: Path) -> None:
    sha256 = "6" * 64
    content_uid = sha256
    artifacts = _install_parsed_tree(
        workspace,
        sha256=sha256,
        content_uid=content_uid,
        fixture_dir=MARKITDOWN_FIXTURE,
    )
    parse_result = _parse_result(
        sha256=sha256,
        content_uid=content_uid,
        parsed_dir=artifacts["parsed_dir"].as_posix(),
        manifest_path=artifacts["parse_manifest"].as_posix(),
        text_path=artifacts["parsed_text"].as_posix(),
        metadata_path=artifacts["parsed_metadata"].as_posix(),
    )
    service, _factory = _service(workspace, parse_results=[parse_result])
    report_path = workspace / "reports" / "evidence_build_report.json"

    result = service.build(
        content_uid=content_uid,
        force=True,
        output=report_path,
    )

    assert result.report_path == report_path
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["report_type"] == REPORT_TYPE
    assert payload["schema_version"] == "1.0"
    assert payload["summary"]["chunks_upserted"] > 0


def test_chinese_path_and_content(workspace: Path) -> None:
    sha256 = "7" * 64
    content_uid = sha256
    chinese_dir = workspace / "parsed" / "中文路径" / "银行项目" / sha256[:2] / sha256[2:4] / sha256
    chinese_dir.mkdir(parents=True)
    artifacts = build_parsed_artifact_paths(chinese_dir)
    chinese_text = (CHINESE_FIXTURE / "方案.txt").read_text(encoding="utf-8")
    parsed_body = f"# 中文标题\n\n{chinese_text}\n"
    artifacts["parsed_text"].write_text(parsed_body, encoding="utf-8")
    artifacts["parsed_metadata"].write_text(
        json.dumps({"parser_name": "markitdown"}, ensure_ascii=False),
        encoding="utf-8",
    )
    manifest = {
        "content_uid": content_uid,
        "sha256": sha256,
        "parser_name": "markitdown",
        "parser_adapter_version": "test-adapter-v1",
        "parsed_text_path": artifacts["parsed_text"].as_posix(),
        "status": "SUCCESS",
        "generated_at": "2026-01-01T00:00:00Z",
    }
    artifacts["parse_manifest"].write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    parse_result = _parse_result(
        sha256=sha256,
        content_uid=content_uid,
        parsed_dir=chinese_dir.as_posix(),
        manifest_path=artifacts["parse_manifest"].as_posix(),
        text_path=artifacts["parsed_text"].as_posix(),
        metadata_path=artifacts["parsed_metadata"].as_posix(),
    )
    service, factory = _service(workspace, parse_results=[parse_result])

    result = service.build(content_uid=content_uid, force=True)

    assert result.documents_processed == 1
    chunks = list(factory.sessions[-1].chunks.values())
    assert any("中文" in chunk.content for chunk in chunks)


def test_deterministic_uid_generation() -> None:
    content_hash = _content_hash("hello")
    chunk_uid = _chunk_uid(
        content_uid="abc",
        document_uid="abc",
        chunk_index=0,
        content_hash=content_hash,
    )
    evidence_uid = _evidence_uid(
        chunk_uid=chunk_uid,
        source_char_start=0,
        source_char_end=5,
        evidence_type="section_quote",
    )
    assert len(chunk_uid) == 64
    assert len(evidence_uid) == 64
    assert chunk_uid == _chunk_uid(
        content_uid="abc",
        document_uid="abc",
        chunk_index=0,
        content_hash=content_hash,
    )


def test_cli_build_evidence_chain_smoke(workspace: Path) -> None:
    sha256 = "8" * 64
    content_uid = sha256
    config = _test_config(workspace)
    config_path = workspace / "app.yaml"
    config_path.write_text("placeholder", encoding="utf-8")

    with patch("app.cli.main.load_config", return_value=config), patch(
        "app.cli.main.EvidenceChainService"
    ) as service_cls:
        service_instance = MagicMock()
        service_instance.build.return_value = EvidenceChainBuildResult(
            candidates_selected=1,
            documents_processed=1,
            documents_skipped=0,
            chunks_planned=2,
            chunks_upserted=0,
            evidence_planned=2,
            evidence_upserted=0,
        )
        service_cls.return_value = service_instance

        result = cli_runner.invoke(
            app,
            [
                "build-evidence-chain",
                "--config",
                str(config_path),
                "--content-uid",
                content_uid,
                "--dry-run",
            ],
        )

    assert result.exit_code == 0
    service_instance.build.assert_called_once()
    kwargs = service_instance.build.call_args.kwargs
    assert kwargs["content_uid"] == content_uid
    assert kwargs["dry_run"] is True


def test_cli_help_documents_contract() -> None:
    result = cli_runner.invoke(app, ["build-evidence-chain", "--help"])
    assert result.exit_code == 0
    assert "parsed_text.md" in result.stdout
    assert "kb_document_chunk" in result.stdout
    assert "--dry-run" in result.stdout
