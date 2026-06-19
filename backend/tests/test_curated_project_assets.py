from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.dialects import mysql
from typer.testing import CliRunner

from app.cli.main import app
from app.core.config import AppConfig, MysqlConfig, RawConfig, StorageConfig
from app.models.document import KbDocument
from app.models.evidence import KbEvidence
from app.models.project import KbCuratedAsset, KbProject, KbProjectDocument
from app.services.curated_project_assets import (
    ASSET_FILES,
    GENERATION_METHOD,
    REPORT_TYPE,
    VERSION_NO,
    CuratedProjectAssetsService,
    curated_uid_for,
    project_uid_for,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = PROJECT_ROOT / "backend/tests/fixtures/curated_project"
DEMO_MANIFEST = FIXTURE_DIR / "demo_project.manifest.yaml.fixture"
CHINESE_MANIFEST = FIXTURE_DIR / "chinese_project.manifest.yaml.fixture"

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


def _extract_filter_value(stmt_text: str, column: str) -> str | None:
    marker = f"{column} = '"
    if marker not in stmt_text:
        return None
    start = stmt_text.index(marker) + len(marker)
    end = stmt_text.index("'", start)
    return stmt_text[start:end]


def _extract_in_values(stmt_text: str, column: str) -> list[str]:
    marker = f"{column} IN ("
    if marker not in stmt_text:
        return []
    start = stmt_text.index(marker) + len(marker)
    end = stmt_text.index(")", start)
    fragment = stmt_text[start:end]
    return [part.strip().strip("'") for part in fragment.split(",") if part.strip()]


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


class _FakeSession:
    def __init__(
        self,
        *,
        documents: dict[str, KbDocument],
        evidence: dict[str, KbEvidence],
        projects: dict[str, KbProject] | None = None,
        project_documents: list[KbProjectDocument] | None = None,
        curated_assets: dict[str, KbCuratedAsset] | None = None,
    ) -> None:
        self.documents = documents
        self.evidence = evidence
        self.projects = projects if projects is not None else {}
        self.project_documents = project_documents if project_documents is not None else []
        self.curated_assets = curated_assets if curated_assets is not None else {}
        self.committed = False
        self.executed_writes = 0

    def scalar(self, stmt):
        stmt_text = _stmt_text(stmt)
        if "kb_document" in stmt_text:
            content_uid = _extract_filter_value(stmt_text, "content_uid")
            if content_uid:
                matches = [
                    doc for doc in self.documents.values() if doc.content_uid == content_uid
                ]
                matches.sort(key=lambda row: row.id, reverse=True)
                return matches[0] if matches else None
        if "kb_project" in stmt_text and "kb_project_document" not in stmt_text:
            project_uid = _extract_filter_value(stmt_text, "project_uid")
            if project_uid:
                return self.projects.get(project_uid)
        if "kb_curated_asset" in stmt_text:
            curated_uid = _extract_filter_value(stmt_text, "curated_uid")
            if curated_uid:
                return self.curated_assets.get(curated_uid)
        return None

    def scalars(self, stmt):
        stmt_text = _stmt_text(stmt)
        if "kb_project_document" in stmt_text:
            project_uid = _extract_filter_value(stmt_text, "project_uid")
            rows = [
                row for row in self.project_documents if row.project_uid == project_uid
            ]
            rows.sort(key=lambda row: row.id)
            limit = _extract_limit(stmt_text)
            if limit is not None:
                rows = rows[:limit]
            return _ScalarResult(rows)
        if "kb_document" in stmt_text and "document_uid IN" in stmt_text:
            uids = _extract_in_values(stmt_text, "document_uid")
            rows = [self.documents[uid] for uid in uids if uid in self.documents]
            return _ScalarResult(rows)
        if "kb_evidence" in stmt_text:
            content_uids = _extract_in_values(stmt_text, "content_uid")
            rows = [
                row
                for row in self.evidence.values()
                if row.content_uid in content_uids
            ]
            rows.sort(key=lambda row: row.id)
            return _ScalarResult(rows)
        return _ScalarResult([])

    def execute(self, stmt) -> None:
        compiled = str(stmt)
        try:
            values = dict(stmt.compile(dialect=mysql.dialect()).params)
        except Exception:
            values = _extract_insert_values(stmt)
        if "kb_project" in compiled and values.get("project_uid"):
            self.executed_writes += 1
            uid = values["project_uid"]
            self.projects[uid] = KbProject(
                id=len(self.projects) + 1,
                project_uid=uid,
                project_code=values.get("project_code", ""),
                project_name=values.get("project_name", ""),
                client_name=None,
                domain=None,
                project_type=None,
                year_start=None,
                year_end=None,
                description=values.get("description"),
                aliases=None,
                keywords=None,
                document_count=values.get("document_count", 0),
                core_document_count=0,
                completeness_score=None,
                has_requirement_doc=0,
                has_solution_doc=0,
                has_design_doc=0,
                has_delivery_doc=0,
                has_acceptance_doc=0,
                has_training_doc=0,
                value_score=None,
                status=values.get("status", "ACTIVE"),
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
        if "kb_project_document" in compiled and values.get("project_uid"):
            self.executed_writes += 1
            key = (values["project_uid"], values["document_uid"])
            existing = next(
                (
                    row
                    for row in self.project_documents
                    if (row.project_uid, row.document_uid) == key
                ),
                None,
            )
            if existing is None:
                self.project_documents.append(
                    KbProjectDocument(
                        id=len(self.project_documents) + 1,
                        project_uid=values["project_uid"],
                        document_uid=values["document_uid"],
                        content_uid=values["content_uid"],
                        candidate_project_code=None,
                        candidate_confidence=None,
                        confirmed_project_code=values.get("confirmed_project_code"),
                        confirmed_by=None,
                        confirmed_at=None,
                        mapping_method=values.get("mapping_method"),
                        confidence=None,
                        is_primary=values.get("is_primary", 1),
                        created_at=datetime.now(),
                    )
                )
            else:
                existing.content_uid = values["content_uid"]
                existing.confirmed_project_code = values.get("confirmed_project_code")
                existing.mapping_method = values.get("mapping_method")
        if "kb_curated_asset" in compiled and values.get("curated_uid"):
            self.executed_writes += 1
            uid = values["curated_uid"]
            self.curated_assets[uid] = KbCuratedAsset(
                id=len(self.curated_assets) + 1,
                curated_uid=uid,
                project_uid=values.get("project_uid"),
                asset_type=values.get("asset_type", ""),
                asset_title=values.get("asset_title"),
                curated_path=values.get("curated_path", ""),
                related_content_uids=values.get("related_content_uids"),
                related_document_uids=values.get("related_document_uids"),
                related_evidence_uids=values.get("related_evidence_uids"),
                generation_method=values.get("generation_method"),
                generation_status=values.get("generation_status"),
                version_no=values.get("version_no", VERSION_NO),
                metadata_json=values.get("metadata"),
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        pass

    def __enter__(self) -> _FakeSession:
        return self

    def __exit__(self, *args) -> None:
        return None


class _ScalarResult:
    def __init__(self, items: list) -> None:
        self._items = items

    def all(self) -> list:
        return list(self._items)


def _session_factory(
    *,
    documents: dict[str, KbDocument],
    evidence: dict[str, KbEvidence],
    projects: dict[str, KbProject] | None = None,
    project_documents: list[KbProjectDocument] | None = None,
    curated_assets: dict[str, KbCuratedAsset] | None = None,
) -> Callable[[], _FakeSession]:
    sessions: list[_FakeSession] = []
    shared_projects = projects if projects is not None else {}
    shared_documents = project_documents if project_documents is not None else []
    shared_curated = curated_assets if curated_assets is not None else {}

    def factory() -> _FakeSession:
        session = _FakeSession(
            documents=documents,
            evidence=evidence,
            projects=shared_projects,
            project_documents=list(shared_documents),
            curated_assets=shared_curated,
        )
        sessions.append(session)
        return session

    factory.sessions = sessions  # type: ignore[attr-defined]
    factory.shared_projects = shared_projects  # type: ignore[attr-defined]
    factory.shared_curated = shared_curated  # type: ignore[attr-defined]
    factory.shared_documents = shared_documents  # type: ignore[attr-defined]
    return factory


def _document(
    *,
    document_uid: str,
    content_uid: str,
    title: str = "Demo Doc",
    parser_name: str = "markitdown",
) -> KbDocument:
    return KbDocument(
        id=1,
        document_uid=document_uid,
        content_uid=content_uid,
        source_sha256=content_uid,
        title=title,
        document_type="txt",
        parser_name=parser_name,
        parser_version="1.0",
        parser_profile="default_v1",
        pipeline_version="v1.1",
        markdown_path=None,
        json_path=None,
        manifest_path=None,
        quality_path=None,
        output_dir=None,
        page_count=None,
        slide_count=None,
        table_count=None,
        image_count=None,
        heading_count=None,
        text_length=None,
        parse_status="SUCCESS",
        quality_status=None,
        quality_score=None,
        metadata_json=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


def _evidence(
    *,
    evidence_uid: str,
    document_uid: str,
    content_uid: str,
    quote_text: str = "示例引用",
    page_no: int | None = 1,
    project_uid: str | None = None,
) -> KbEvidence:
    return KbEvidence(
        id=1,
        evidence_uid=evidence_uid,
        project_uid=project_uid,
        document_uid=document_uid,
        content_uid=content_uid,
        chunk_uid="chunk_test",
        evidence_type="section_quote",
        source_file_path=None,
        source_sha256=content_uid,
        source_page_start=page_no,
        source_page_end=page_no,
        source_char_start=0,
        source_char_end=10,
        page_no=page_no,
        slide_no=None,
        heading_path="# Intro",
        bbox=None,
        quote_text=quote_text,
        normalized_text=None,
        source_location="parsed_text.md:0-10",
        confidence=None,
        metadata_json=None,
        created_at=datetime.now(),
    )


def _demo_seed() -> tuple[dict[str, KbDocument], dict[str, KbEvidence]]:
    content_uid = "a" * 64
    document_uid = "doc_demo_001"
    documents = {document_uid: _document(document_uid=document_uid, content_uid=content_uid)}
    evidence = {
        "ev_demo_001": _evidence(
            evidence_uid="ev_demo_001",
            document_uid=document_uid,
            content_uid=content_uid,
        )
    }
    return documents, evidence


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "workspace"
    for name in ("parsed", "raw_vault", "curated", "reports"):
        (root / name).mkdir(parents=True)
    return root


def _service(
    workspace: Path,
    *,
    documents: dict[str, KbDocument],
    evidence: dict[str, KbEvidence],
    projects: dict[str, KbProject] | None = None,
    project_documents: list[KbProjectDocument] | None = None,
    curated_assets: dict[str, KbCuratedAsset] | None = None,
) -> tuple[CuratedProjectAssetsService, Callable]:
    config = _test_config(workspace)
    factory = _session_factory(
        documents=documents,
        evidence=evidence,
        projects=projects,
        project_documents=project_documents,
        curated_assets=curated_assets,
    )
    service = CuratedProjectAssetsService(config, session_factory=factory)
    return service, factory


def _project_dir(workspace: Path, project_code: str) -> Path:
    return workspace / "curated" / "projects" / project_code


def test_dry_run_zero_db_and_file_writes(workspace: Path) -> None:
    documents, evidence = _demo_seed()
    service, factory = _service(workspace, documents=documents, evidence=evidence)

    result = service.build(
        project_code="DEMO-2024",
        project_name="Demo Project",
        manifest_path=DEMO_MANIFEST,
        dry_run=True,
        output=workspace / "reports" / "dry_run.json",
    )

    assert result.documents_mapped == 1
    assert factory.sessions[-1].executed_writes == 0
    assert not any(_project_dir(workspace, "DEMO-2024").rglob("*"))
    report = json.loads((workspace / "reports" / "dry_run.json").read_text(encoding="utf-8"))
    assert report["report_type"] == REPORT_TYPE
    assert report["dry_run"] is True


def test_first_run_writes_three_files_and_upserts_tables(workspace: Path) -> None:
    documents, evidence = _demo_seed()
    service, factory = _service(workspace, documents=documents, evidence=evidence)

    result = service.build(
        project_code="DEMO-2024",
        project_name="Demo Project",
        manifest_path=DEMO_MANIFEST,
        force=True,
    )

    project_dir = _project_dir(workspace, "DEMO-2024")
    assert result.assets_written == 3
    assert result.files_written == 3
    for filename in ASSET_FILES.values():
        assert (project_dir / filename).is_file()
    session = factory.sessions[-1]
    assert len(session.projects) == 1
    assert len(session.project_documents) == 1
    assert len(session.curated_assets) == 3
    card = session.curated_assets[curated_uid_for("DEMO-2024", "project_card")]
    assert card.generation_method == GENERATION_METHOD
    assert card.related_evidence_uids == ["ev_demo_001"]


def test_no_force_rerun_skips_without_duplicate_rows(workspace: Path) -> None:
    documents, evidence = _demo_seed()
    service, factory = _service(workspace, documents=documents, evidence=evidence)

    first = service.build(
        project_code="DEMO-2024",
        project_name="Demo Project",
        manifest_path=DEMO_MANIFEST,
        force=True,
    )
    mtimes = {
        path: path.stat().st_mtime
        for path in _project_dir(workspace, "DEMO-2024").glob("*.md")
    }

    second = service.build(
        project_code="DEMO-2024",
        project_name="Demo Project",
        manifest_path=DEMO_MANIFEST,
        force=False,
    )

    assert first.assets_written == 3
    assert second.assets_written == 0
    assert second.assets_skipped == 3
    session = factory.sessions[-1]
    assert len(session.projects) == 1
    assert len(session.curated_assets) == 3
    for path, mtime in mtimes.items():
        assert path.stat().st_mtime == mtime


def test_force_rerun_overwrites_files_same_uids(workspace: Path) -> None:
    documents, evidence = _demo_seed()
    service, factory = _service(workspace, documents=documents, evidence=evidence)

    service.build(
        project_code="DEMO-2024",
        project_name="Demo Project",
        manifest_path=DEMO_MANIFEST,
        force=True,
    )
    card_path = _project_dir(workspace, "DEMO-2024") / ASSET_FILES["project_card"]
    card_path.write_text("# stale", encoding="utf-8")

    result = service.build(
        project_code="DEMO-2024",
        project_name="Demo Project",
        manifest_path=DEMO_MANIFEST,
        force=True,
    )

    assert result.assets_written == 3
    assert "Project Card:" in card_path.read_text(encoding="utf-8")
    uids = set(factory.shared_curated)
    assert len(uids) == 3
    assert all(asset.version_no == VERSION_NO for asset in factory.shared_curated.values())


def test_related_json_arrays_correct(workspace: Path) -> None:
    documents, evidence = _demo_seed()
    service, factory = _service(workspace, documents=documents, evidence=evidence)

    service.build(
        project_code="DEMO-2024",
        project_name="Demo Project",
        manifest_path=DEMO_MANIFEST,
        force=True,
    )

    asset = factory.shared_curated[curated_uid_for("DEMO-2024", "evidence_index")]
    assert asset.related_content_uids == ["a" * 64]
    assert asset.related_document_uids == ["doc_demo_001"]
    assert asset.related_evidence_uids == ["ev_demo_001"]


def test_chinese_project_name_utf8(workspace: Path) -> None:
    content_uid = "b" * 64
    document_uid = "doc_cn_001"
    documents = {
        document_uid: _document(
            document_uid=document_uid,
            content_uid=content_uid,
            title="中文文档",
        )
    }
    evidence = {
        "ev_cn_001": _evidence(
            evidence_uid="ev_cn_001",
            document_uid=document_uid,
            content_uid=content_uid,
            quote_text="中文引用内容",
        )
    }
    service, _factory = _service(workspace, documents=documents, evidence=evidence)
    project_code = "中文项目-2024"

    service.build(
        project_code=project_code,
        manifest_path=CHINESE_MANIFEST,
        force=True,
    )

    card = _project_dir(workspace, project_code) / ASSET_FILES["project_card"]
    text = card.read_text(encoding="utf-8")
    assert "银行项目梳理" in text
    assert project_uid_for(project_code) in text


def test_no_evidence_warning_without_crash(workspace: Path) -> None:
    content_uid = "c" * 64
    document_uid = "doc_no_evidence"
    documents = {document_uid: _document(document_uid=document_uid, content_uid=content_uid)}
    service, factory = _service(workspace, documents=documents, evidence={})

    result = service.build(
        project_code="DEMO-2024",
        project_name="Demo Project",
        content_uid=content_uid,
        force=True,
    )

    assert result.documents_mapped == 1
    assert result.warnings
    assert result.assets_written == 3
    index_asset = factory.shared_curated[curated_uid_for("DEMO-2024", "evidence_index")]
    assert index_asset.generation_status == "SKIPPED"


def test_does_not_read_raw_vault_binary(workspace: Path, monkeypatch) -> None:
    documents, evidence = _demo_seed()
    service, _factory = _service(workspace, documents=documents, evidence=evidence)
    original_open = Path.open
    opened: list[Path] = []

    def tracking_open(self, *args, **kwargs):
        opened.append(self)
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", tracking_open)

    service.build(
        project_code="DEMO-2024",
        project_name="Demo Project",
        manifest_path=DEMO_MANIFEST,
        force=True,
    )

    assert not any(path.name == "original.bin" for path in opened)


def test_parsed_files_not_modified(workspace: Path) -> None:
    documents, evidence = _demo_seed()
    parsed_file = workspace / "parsed" / "parsed_text.md"
    parsed_file.write_text("parsed content", encoding="utf-8")
    before = parsed_file.stat().st_mtime
    service, _factory = _service(workspace, documents=documents, evidence=evidence)

    service.build(
        project_code="DEMO-2024",
        project_name="Demo Project",
        manifest_path=DEMO_MANIFEST,
        force=True,
    )

    assert parsed_file.stat().st_mtime == before


def test_does_not_call_parser_services(workspace: Path) -> None:
    documents, evidence = _demo_seed()
    service, _factory = _service(workspace, documents=documents, evidence=evidence)

    with patch("app.services.markitdown_parser.MarkItDownParserService") as markitdown_mock, patch(
        "app.services.mineru_pdf_parser.MineruPdfParserService"
    ) as mineru_mock:
        markitdown_mock.return_value = MagicMock()
        mineru_mock.return_value = MagicMock()
        service.build(
            project_code="DEMO-2024",
            project_name="Demo Project",
            manifest_path=DEMO_MANIFEST,
            force=True,
        )

    markitdown_mock.assert_not_called()
    mineru_mock.assert_not_called()


def test_forbidden_tables_not_written(workspace: Path) -> None:
    documents, evidence = _demo_seed()
    service, factory = _service(workspace, documents=documents, evidence=evidence)

    service.build(
        project_code="DEMO-2024",
        project_name="Demo Project",
        manifest_path=DEMO_MANIFEST,
        force=True,
    )

    session = factory.sessions[-1]
    assert len(session.evidence) == 1
    assert session.evidence["ev_demo_001"].project_uid is None


def test_markdown_contains_traceability_uids(workspace: Path) -> None:
    documents, evidence = _demo_seed()
    service, _factory = _service(workspace, documents=documents, evidence=evidence)

    service.build(
        project_code="DEMO-2024",
        project_name="Demo Project",
        manifest_path=DEMO_MANIFEST,
        force=True,
    )

    index = (
        _project_dir(workspace, "DEMO-2024") / ASSET_FILES["evidence_index"]
    ).read_text(encoding="utf-8")
    assert "ev_demo_001" in index
    assert "doc_demo_001" in index
    assert "a" * 64 in index


def test_seed_mapping_method(workspace: Path) -> None:
    content_uid = "d" * 64
    document_uid = "doc_seed_001"
    documents = {document_uid: _document(document_uid=document_uid, content_uid=content_uid)}
    project_uid = project_uid_for("SEED-PROJ")
    project_documents = [
        KbProjectDocument(
            id=1,
            project_uid=project_uid,
            document_uid=document_uid,
            content_uid=content_uid,
            candidate_project_code=None,
            candidate_confidence=None,
            confirmed_project_code="SEED-PROJ",
            confirmed_by=None,
            confirmed_at=None,
            mapping_method="SEED",
            confidence=None,
            is_primary=1,
            created_at=datetime.now(),
        )
    ]
    service, factory = _service(
        workspace,
        documents=documents,
        evidence={},
        project_documents=project_documents,
    )

    service.build(
        project_code="SEED-PROJ",
        project_name="Seed Project",
        force=True,
    )

    mapping = factory.shared_documents[0]
    assert mapping.mapping_method == "SEED"


def test_cli_smoke_dry_run(workspace: Path, monkeypatch) -> None:
    documents, evidence = _demo_seed()
    config_path = workspace / "app.yaml"
    config_path.write_text(
        f"""
app:
  pipeline_version: v1.1
storage:
  source_registry_root: {workspace / "source_registry"}
  raw_vault_root: {workspace / "raw_vault"}
  parsed_root: {workspace / "parsed"}
  curated_root: {workspace / "curated"}
  quarantine_root: {workspace / "quarantine"}
  reports_root: {workspace / "reports"}
mysql:
  host: 127.0.0.1
  port: 3306
  database: personal_kb
  username: personal_kb
  password: test
  charset: utf8mb4
raw:
  original_files_readonly: true
  copy_unique_content_to_vault: true
""".strip(),
        encoding="utf-8",
    )

    def fake_factory():
        return _FakeSession(documents=documents, evidence=evidence)

    monkeypatch.setattr(
        "app.services.curated_project_assets.create_db_engine",
        lambda _config: object(),
    )
    monkeypatch.setattr(
        "app.services.curated_project_assets.create_session_factory",
        lambda _engine: fake_factory,
    )

    result = cli_runner.invoke(
        app,
        [
            "build-curated-project",
            "--config",
            str(config_path),
            "--project-code",
            "DEMO-2024",
            "--project-name",
            "Demo Project",
            "--manifest",
            str(DEMO_MANIFEST),
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    assert "Dry run: True" in result.stdout
    assert not any(_project_dir(workspace, "DEMO-2024").rglob("*"))


def test_manifest_project_code_mismatch_raises(workspace: Path) -> None:
    documents, evidence = _demo_seed()
    service, _factory = _service(workspace, documents=documents, evidence=evidence)

    with pytest.raises(ValueError, match="does not match"):
        service.build(
            project_code="OTHER-CODE",
            project_name="Demo Project",
            manifest_path=DEMO_MANIFEST,
        )


def test_limit_truncates_manifest_documents(workspace: Path) -> None:
    content_uid_a = "a" * 64
    content_uid_b = "b" * 64
    documents = {
        "doc_a": _document(document_uid="doc_a", content_uid=content_uid_a),
        "doc_b": _document(document_uid="doc_b", content_uid=content_uid_b),
    }
    manifest_path = workspace / "multi.manifest.yaml.fixture"
    manifest_path.write_text(
        f"""
project_code: MULTI-2024
project_name: Multi Doc
documents:
  - content_uid: "{content_uid_a}"
    document_uid: doc_a
  - content_uid: "{content_uid_b}"
    document_uid: doc_b
""".strip(),
        encoding="utf-8",
    )
    service, factory = _service(workspace, documents=documents, evidence={})

    result = service.build(
        project_code="MULTI-2024",
        manifest_path=manifest_path,
        limit=1,
        force=True,
    )

    assert result.documents_mapped == 1
    assert len(factory.sessions[-1].project_documents) == 1


def test_only_three_markdown_files_written(workspace: Path) -> None:
    documents, evidence = _demo_seed()
    service, _factory = _service(workspace, documents=documents, evidence=evidence)

    service.build(
        project_code="DEMO-2024",
        project_name="Demo Project",
        manifest_path=DEMO_MANIFEST,
        force=True,
    )

    project_dir = _project_dir(workspace, "DEMO-2024")
    md_files = sorted(path.name for path in project_dir.glob("*.md"))
    assert md_files == sorted(ASSET_FILES.values())


def test_cli_content_uid_mapping_method(workspace: Path) -> None:
    content_uid = "e" * 64
    document_uid = "doc_cli_001"
    documents = {document_uid: _document(document_uid=document_uid, content_uid=content_uid)}
    service, factory = _service(workspace, documents=documents, evidence={})

    service.build(
        project_code="CLI-PROJ",
        project_name="CLI Project",
        content_uid=content_uid,
        force=True,
    )

    assert factory.sessions[-1].project_documents[0].mapping_method == "CLI"
