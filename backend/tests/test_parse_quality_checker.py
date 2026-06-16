from __future__ import annotations

import json
import subprocess
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from app.cli.main import app
from app.core.config import AppConfig, MysqlConfig, RawConfig, StorageConfig, load_config
from app.core.parsed_paths import build_parsed_artifact_paths, build_parsed_content_dir
from app.core.vault_paths import build_vault_artifact_paths, build_vault_dir
from app.models.file import KbFileContent
from app.models.parse_registry import KbParsedArtifact, KbParseResult
from app.models.vault import KbRawVaultObject
from app.services.parse_quality_checker import (
    ISSUE_CODES,
    SCHEMA_VERSION,
    ParseQualityCheckerService,
    ParseQualityCandidate,
)

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
        vault_objects: dict[str, KbRawVaultObject],
        artifacts: dict[tuple[str, str], list[KbParsedArtifact]],
        file_contents: dict[str, KbFileContent],
    ) -> None:
        self.vault_objects = vault_objects
        self.artifacts = artifacts
        self.file_contents = file_contents

    def scalar(self, stmt) -> object | None:
        stmt_text = _stmt_text(stmt)
        if "kb_raw_vault_object" in stmt_text:
            for sha256, vault_object in self.vault_objects.items():
                if sha256 in stmt_text:
                    return vault_object
        if "kb_file_content" in stmt_text:
            for sha256, content in self.file_contents.items():
                if sha256 in stmt_text:
                    return content
        return None

    def scalars(self, stmt):
        stmt_text = _stmt_text(stmt)
        if "kb_parsed_artifact" not in stmt_text:
            return _ScalarResult([])
        matches: list[KbParsedArtifact] = []
        for (run_uid, content_uid), items in self.artifacts.items():
            if run_uid in stmt_text and content_uid in stmt_text:
                matches.extend(items)
        return _ScalarResult(matches)

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
    vault_objects: dict[str, KbRawVaultObject] | None = None,
    artifacts: dict[tuple[str, str], list[KbParsedArtifact]] | None = None,
    file_contents: dict[str, KbFileContent] | None = None,
) -> Callable[[], _FakeSession]:
    def factory() -> _FakeSession:
        return _FakeSession(
            vault_objects=vault_objects or {},
            artifacts=artifacts or {},
            file_contents=file_contents or {},
        )

    return factory


def _parse_result(
    *,
    sha256: str,
    content_uid: str,
    parser_name: str = "markitdown",
    status: str = "SUCCESS",
    run_uid: str = "parse_run_test",
    result_uid: str = "parse_result_test",
    parsed_dir: str | None = None,
    manifest_path: str | None = None,
    source_vault_path: str | None = None,
    error_code: str | None = None,
    route_type: str | None = "OFFICE_DOCX",
) -> KbParseResult:
    return KbParseResult(
        id=1,
        result_uid=result_uid,
        run_uid=run_uid,
        content_uid=content_uid,
        sha256=sha256,
        route_type=route_type,
        decision=None,
        status=status,
        source_vault_path=source_vault_path,
        parsed_dir=parsed_dir,
        manifest_path=manifest_path,
        metadata_path=None,
        text_path=None,
        output_hash=None,
        output_size_bytes=None,
        error_code=error_code,
        error_message=None,
        retry_of_result_id=None,
        parser_name=parser_name,
        parser_adapter_version="test-adapter-v1",
        pipeline_version="v1.1",
        metadata_json=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


def _vault_object(
    *,
    sha256: str,
    content_uid: str,
    vault_path: str,
) -> KbRawVaultObject:
    return KbRawVaultObject(
        id=1,
        vault_uid=sha256,
        content_uid=content_uid,
        sha256=sha256,
        vault_path=vault_path,
        original_name="sample.txt",
        source_paths_json_path=None,
        file_metadata_json_path=None,
        copy_status="COPIED",
        copied_at=None,
        error_message=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


def _file_content(*, sha256: str, content_uid: str) -> KbFileContent:
    return KbFileContent(
        id=1,
        content_uid=content_uid,
        sha256=sha256,
        file_ext=".txt",
        mime_type="text/plain",
        file_size=10,
        master_file_instance_uid=None,
        instance_count=1,
        vault_path="",
        vault_status="COPIED",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


def _artifact(
    *,
    run_uid: str,
    content_uid: str,
    sha256: str,
    artifact_type: str,
    artifact_path: str,
    parser_name: str = "markitdown",
) -> KbParsedArtifact:
    return KbParsedArtifact(
        id=1,
        artifact_uid=f"artifact_{artifact_type.lower()}",
        run_uid=run_uid,
        content_uid=content_uid,
        sha256=sha256,
        artifact_type=artifact_type,
        artifact_path=artifact_path,
        artifact_hash=None,
        artifact_size_bytes=None,
        parser_name=parser_name,
        parser_adapter_version="test-adapter-v1",
        status="INDEXED",
        metadata_json=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


def _write_valid_manifest(
    artifacts: dict[str, Path],
    *,
    content_uid: str,
    sha256: str,
    parser_name: str = "markitdown",
    source_vault_path: str,
) -> None:
    manifest = {
        "content_uid": content_uid,
        "sha256": sha256,
        "route_type": "OFFICE_DOCX",
        "parser_name": parser_name,
        "parser_adapter_version": "test-adapter-v1",
        "source_vault_path": source_vault_path,
        "parsed_text_path": artifacts["parsed_text"].as_posix(),
        "parsed_metadata_path": artifacts["parsed_metadata"].as_posix(),
        "generated_at": "2026-01-01T00:00:00Z",
        "status": "SUCCESS",
    }
    if parser_name == "mineru":
        manifest["parser_profile"] = "mineru_default_v1"
    artifacts["parsed_text"].write_text("# sample\n", encoding="utf-8")
    artifacts["parsed_metadata"].write_text("{}", encoding="utf-8")
    artifacts["parse_manifest"].write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    for name in ("raw_vault", "parsed", "reports"):
        (tmp_path / name).mkdir()
    return tmp_path


def _checker(
    workspace: Path,
    *,
    candidates: list[ParseQualityCandidate] | None = None,
    parse_results: list[KbParseResult] | None = None,
    vault_objects: dict[str, KbRawVaultObject] | None = None,
    artifacts: dict[tuple[str, str], list[KbParsedArtifact]] | None = None,
    file_contents: dict[str, KbFileContent] | None = None,
) -> ParseQualityCheckerService:
    config = _test_config(workspace)
    service = ParseQualityCheckerService(
        config,
        session_factory=_session_factory(
            vault_objects=vault_objects,
            artifacts=artifacts,
            file_contents=file_contents,
        ),
    )
    if candidates is not None:
        service._load_candidates = (  # type: ignore[method-assign]
            lambda **kwargs: candidates
        )
    elif parse_results is not None:
        service._load_candidates = (  # type: ignore[method-assign]
            lambda **kwargs: [
                ParseQualityCandidate(
                    content_uid=result.content_uid,
                    sha256=result.sha256,
                    parser_name=result.parser_name,
                    parser_adapter_version=result.parser_adapter_version,
                    result_status=result.status,
                    route_type=result.route_type,
                    run_uid=result.run_uid,
                    result_uid=result.result_uid,
                    parsed_dir=result.parsed_dir,
                    manifest_path=result.manifest_path,
                    source_vault_path=result.source_vault_path,
                    error_code=result.error_code,
                )
                for result in parse_results
            ]
        )
    return service


def test_tc001_valid_parsed_artifact_set(workspace: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.parse_quality_checker.STALE_PATH_MARKERS",
        ("/tmp/p5_reqa_", "/var/tmp/p5_reqa_"),
    )
    sha256 = "a" * 64
    content_uid = sha256
    vault_dir = build_vault_dir(workspace / "raw_vault", sha256)
    vault_dir.mkdir(parents=True)
    build_vault_artifact_paths(vault_dir)["original_bin"].write_bytes(b"data")
    parsed_dir = build_parsed_content_dir(workspace / "parsed", sha256)
    artifacts = build_parsed_artifact_paths(parsed_dir)
    parsed_dir.mkdir(parents=True)
    _write_valid_manifest(
        artifacts,
        content_uid=content_uid,
        sha256=sha256,
        source_vault_path=build_vault_artifact_paths(vault_dir)["original_bin"].as_posix(),
    )

    parse_result = _parse_result(
        sha256=sha256,
        content_uid=content_uid,
        parsed_dir=parsed_dir.as_posix(),
        manifest_path=artifacts["parse_manifest"].as_posix(),
        source_vault_path=build_vault_artifact_paths(vault_dir)["original_bin"].as_posix(),
    )
    registry_artifacts = {
        (parse_result.run_uid, content_uid): [
            _artifact(
                run_uid=parse_result.run_uid,
                content_uid=content_uid,
                sha256=sha256,
                artifact_type="PARSED_TEXT",
                artifact_path=artifacts["parsed_text"].as_posix(),
            ),
            _artifact(
                run_uid=parse_result.run_uid,
                content_uid=content_uid,
                sha256=sha256,
                artifact_type="PARSED_METADATA",
                artifact_path=artifacts["parsed_metadata"].as_posix(),
            ),
            _artifact(
                run_uid=parse_result.run_uid,
                content_uid=content_uid,
                sha256=sha256,
                artifact_type="PARSE_MANIFEST",
                artifact_path=artifacts["parse_manifest"].as_posix(),
            ),
        ]
    }
    service = _checker(
        workspace,
        parse_results=[parse_result],
        vault_objects={sha256: _vault_object(sha256=sha256, content_uid=content_uid, vault_path=vault_dir.as_posix())},
        artifacts=registry_artifacts,
        file_contents={sha256: _file_content(sha256=sha256, content_uid=content_uid)},
    )
    report = service.check()
    assert report.summary["issue_count"] == 0
    assert report.summary["error_count"] == 0
    assert report.summary["critical_count"] == 0
    payload = report.to_dict()
    assert payload["schema_version"] == SCHEMA_VERSION
    assert set(payload["issue_counts"]) == set(ISSUE_CODES)


def test_tc002_missing_raw_vault_object(workspace: Path) -> None:
    sha256 = "b" * 64
    content_uid = sha256
    vault_dir = build_vault_dir(workspace / "raw_vault", sha256)
    vault_dir.mkdir(parents=True)
    parse_result = _parse_result(sha256=sha256, content_uid=content_uid)
    service = _checker(
        workspace,
        parse_results=[parse_result],
        vault_objects={sha256: _vault_object(sha256=sha256, content_uid=content_uid, vault_path=vault_dir.as_posix())},
    )
    report = service.check()
    codes = [issue.issue_code for issue in report.issues]
    assert "MISSING_RAW_VAULT_OBJECT" in codes
    issue = next(item for item in report.issues if item.issue_code == "MISSING_RAW_VAULT_OBJECT")
    assert issue.severity == "ERROR"


def test_tc003_stale_tmp_raw_vault_path(workspace: Path) -> None:
    sha256 = "c" * 64
    content_uid = sha256
    stale_path = "/tmp/p5_reqa_xxx/by_hash/ab"
    parse_result = _parse_result(
        sha256=sha256,
        content_uid=content_uid,
        source_vault_path=f"{stale_path}/original.bin",
    )
    service = _checker(
        workspace,
        parse_results=[parse_result],
        vault_objects={
            sha256: _vault_object(sha256=sha256, content_uid=content_uid, vault_path=stale_path)
        },
    )
    report = service.check()
    stale_issues = [issue for issue in report.issues if issue.issue_code == "STALE_RAW_VAULT_PATH"]
    assert stale_issues
    assert all(issue.severity == "WARNING" for issue in stale_issues)


def test_tc004_missing_parsed_directory(workspace: Path) -> None:
    sha256 = "d" * 64
    content_uid = sha256
    missing_dir = workspace / "parsed" / "missing"
    parse_result = _parse_result(
        sha256=sha256,
        content_uid=content_uid,
        parsed_dir=missing_dir.as_posix(),
    )
    service = _checker(workspace, parse_results=[parse_result])
    report = service.check()
    issue = next(item for item in report.issues if item.issue_code == "MISSING_PARSED_DIR")
    assert issue.severity == "ERROR"


def test_tc005_missing_parsed_text(workspace: Path) -> None:
    sha256 = "e" * 64
    content_uid = sha256
    parsed_dir = build_parsed_content_dir(workspace / "parsed", sha256)
    artifacts = build_parsed_artifact_paths(parsed_dir)
    parsed_dir.mkdir(parents=True)
    artifacts["parsed_metadata"].write_text("{}", encoding="utf-8")
    artifacts["parse_manifest"].write_text("{}", encoding="utf-8")
    parse_result = _parse_result(
        sha256=sha256,
        content_uid=content_uid,
        parsed_dir=parsed_dir.as_posix(),
        manifest_path=artifacts["parse_manifest"].as_posix(),
    )
    service = _checker(workspace, parse_results=[parse_result])
    report = service.check()
    assert any(issue.issue_code == "MISSING_PARSED_TEXT" for issue in report.issues)


def test_tc007_missing_parse_manifest(workspace: Path) -> None:
    sha256 = "f" * 64
    content_uid = sha256
    parsed_dir = build_parsed_content_dir(workspace / "parsed", sha256)
    artifacts = build_parsed_artifact_paths(parsed_dir)
    parsed_dir.mkdir(parents=True)
    artifacts["parsed_text"].write_text("x", encoding="utf-8")
    artifacts["parsed_metadata"].write_text("{}", encoding="utf-8")
    parse_result = _parse_result(
        sha256=sha256,
        content_uid=content_uid,
        parsed_dir=parsed_dir.as_posix(),
    )
    service = _checker(workspace, parse_results=[parse_result])
    report = service.check()
    assert any(issue.issue_code == "MISSING_PARSE_MANIFEST" for issue in report.issues)


def test_tc008_invalid_manifest_json(workspace: Path) -> None:
    sha256 = "0" * 64
    content_uid = sha256
    parsed_dir = build_parsed_content_dir(workspace / "parsed", sha256)
    artifacts = build_parsed_artifact_paths(parsed_dir)
    parsed_dir.mkdir(parents=True)
    artifacts["parsed_text"].write_text("x", encoding="utf-8")
    artifacts["parsed_metadata"].write_text("{}", encoding="utf-8")
    artifacts["parse_manifest"].write_text("{not-json", encoding="utf-8")
    parse_result = _parse_result(
        sha256=sha256,
        content_uid=content_uid,
        parsed_dir=parsed_dir.as_posix(),
        manifest_path=artifacts["parse_manifest"].as_posix(),
    )
    service = _checker(workspace, parse_results=[parse_result])
    report = service.check()
    issue = next(item for item in report.issues if item.issue_code == "INVALID_PARSE_MANIFEST_JSON")
    assert issue.severity == "ERROR"


def test_tc009_manifest_required_field_missing(workspace: Path) -> None:
    sha256 = "1" * 64
    content_uid = sha256
    parsed_dir = build_parsed_content_dir(workspace / "parsed", sha256)
    artifacts = build_parsed_artifact_paths(parsed_dir)
    parsed_dir.mkdir(parents=True)
    artifacts["parsed_text"].write_text("x", encoding="utf-8")
    artifacts["parsed_metadata"].write_text("{}", encoding="utf-8")
    artifacts["parse_manifest"].write_text(
        json.dumps({"content_uid": content_uid}, ensure_ascii=False),
        encoding="utf-8",
    )
    parse_result = _parse_result(
        sha256=sha256,
        content_uid=content_uid,
        parsed_dir=parsed_dir.as_posix(),
        manifest_path=artifacts["parse_manifest"].as_posix(),
    )
    service = _checker(workspace, parse_results=[parse_result])
    report = service.check()
    assert any(issue.issue_code == "MANIFEST_REQUIRED_FIELD_MISSING" for issue in report.issues)


def test_tc010_manifest_sha256_mismatch(workspace: Path) -> None:
    sha256 = "2" * 64
    content_uid = sha256
    parsed_dir = build_parsed_content_dir(workspace / "parsed", sha256)
    artifacts = build_parsed_artifact_paths(parsed_dir)
    parsed_dir.mkdir(parents=True)
    _write_valid_manifest(
        artifacts,
        content_uid=content_uid,
        sha256="3" * 64,
        source_vault_path="/vault/original.bin",
    )
    parse_result = _parse_result(
        sha256=sha256,
        content_uid=content_uid,
        parsed_dir=parsed_dir.as_posix(),
        manifest_path=artifacts["parse_manifest"].as_posix(),
    )
    service = _checker(
        workspace,
        parse_results=[parse_result],
        file_contents={sha256: _file_content(sha256=sha256, content_uid=content_uid)},
    )
    report = service.check()
    issue = next(item for item in report.issues if item.issue_code == "MANIFEST_SHA256_MISMATCH")
    assert issue.severity == "CRITICAL"


def test_tc011_manifest_content_uid_mismatch(workspace: Path) -> None:
    sha256 = "4" * 64
    content_uid = sha256
    parsed_dir = build_parsed_content_dir(workspace / "parsed", sha256)
    artifacts = build_parsed_artifact_paths(parsed_dir)
    parsed_dir.mkdir(parents=True)
    _write_valid_manifest(
        artifacts,
        content_uid="other-content",
        sha256=sha256,
        source_vault_path="/vault/original.bin",
    )
    parse_result = _parse_result(
        sha256=sha256,
        content_uid=content_uid,
        parsed_dir=parsed_dir.as_posix(),
        manifest_path=artifacts["parse_manifest"].as_posix(),
    )
    service = _checker(workspace, parse_results=[parse_result])
    report = service.check()
    issue = next(
        item for item in report.issues if item.issue_code == "MANIFEST_CONTENT_UID_MISMATCH"
    )
    assert issue.severity == "CRITICAL"


def test_tc012_invalid_parser_name(workspace: Path) -> None:
    sha256 = "5" * 64
    content_uid = sha256
    parsed_dir = build_parsed_content_dir(workspace / "parsed", sha256)
    artifacts = build_parsed_artifact_paths(parsed_dir)
    parsed_dir.mkdir(parents=True)
    _write_valid_manifest(
        artifacts,
        content_uid=content_uid,
        sha256=sha256,
        parser_name="unknown-parser",
        source_vault_path="/vault/original.bin",
    )
    parse_result = _parse_result(
        sha256=sha256,
        content_uid=content_uid,
        parsed_dir=parsed_dir.as_posix(),
        manifest_path=artifacts["parse_manifest"].as_posix(),
    )
    service = _checker(workspace, parse_results=[parse_result])
    report = service.check()
    assert any(issue.issue_code == "MANIFEST_PARSER_NAME_INVALID" for issue in report.issues)


def test_tc013_missing_parser_adapter_version(workspace: Path) -> None:
    sha256 = "6" * 64
    content_uid = sha256
    parsed_dir = build_parsed_content_dir(workspace / "parsed", sha256)
    artifacts = build_parsed_artifact_paths(parsed_dir)
    parsed_dir.mkdir(parents=True)
    artifacts["parsed_text"].write_text("x", encoding="utf-8")
    artifacts["parsed_metadata"].write_text("{}", encoding="utf-8")
    manifest = {
        "content_uid": content_uid,
        "sha256": sha256,
        "parser_name": "markitdown",
        "status": "SUCCESS",
        "generated_at": "2026-01-01T00:00:00Z",
        "parsed_text_path": artifacts["parsed_text"].as_posix(),
        "parsed_metadata_path": artifacts["parsed_metadata"].as_posix(),
    }
    artifacts["parse_manifest"].write_text(json.dumps(manifest), encoding="utf-8")
    parse_result = _parse_result(
        sha256=sha256,
        content_uid=content_uid,
        parsed_dir=parsed_dir.as_posix(),
        manifest_path=artifacts["parse_manifest"].as_posix(),
    )
    service = _checker(workspace, parse_results=[parse_result])
    report = service.check()
    assert any(
        issue.issue_code == "MANIFEST_ADAPTER_VERSION_MISSING" for issue in report.issues
    )


def test_tc014_registry_artifact_path_missing(workspace: Path) -> None:
    sha256 = "7" * 64
    content_uid = sha256
    parse_result = _parse_result(sha256=sha256, content_uid=content_uid)
    artifacts = {
        (parse_result.run_uid, content_uid): [
            _artifact(
                run_uid=parse_result.run_uid,
                content_uid=content_uid,
                sha256=sha256,
                artifact_type="PARSED_TEXT",
                artifact_path="/missing/parsed_text.md",
            )
        ]
    }
    service = _checker(workspace, parse_results=[parse_result], artifacts=artifacts)
    report = service.check()
    issue = next(
        item for item in report.issues if item.issue_code == "REGISTRY_ARTIFACT_PATH_MISSING"
    )
    assert issue.severity == "ERROR"


def test_tc015_registry_success_file_mismatch(workspace: Path) -> None:
    sha256 = "8" * 64
    content_uid = sha256
    parsed_dir = build_parsed_content_dir(workspace / "parsed", sha256)
    parse_result = _parse_result(
        sha256=sha256,
        content_uid=content_uid,
        status="SUCCESS",
        parsed_dir=parsed_dir.as_posix(),
    )
    service = _checker(workspace, parse_results=[parse_result])
    report = service.check()
    issue = next(
        item for item in report.issues if item.issue_code == "REGISTRY_STATUS_FILE_MISMATCH"
    )
    assert issue.severity == "CRITICAL"


def test_tc016_registry_missing_manifest_result(workspace: Path) -> None:
    sha256 = "9" * 64
    content_uid = sha256
    parse_result = _parse_result(
        sha256=sha256,
        content_uid=content_uid,
        status="FAILED",
        error_code="MISSING_MANIFEST",
    )
    service = _checker(workspace, parse_results=[parse_result])
    report = service.check()
    assert report.issue_counts["REGISTRY_MISSING_MANIFEST_RESULT"] == 1


def test_tc017_failed_result_aggregation(workspace: Path) -> None:
    parse_result = _parse_result(
        sha256="a1" * 32,
        content_uid="a1" * 32,
        status="FAILED",
    )
    service = _checker(workspace, parse_results=[parse_result])
    report = service.check()
    assert report.issue_counts["REGISTRY_FAILED_RESULT"] == 1
    assert report.by_status.get("FAILED", 0) >= 1


def test_tc018_empty_result_aggregation(workspace: Path) -> None:
    parse_result = _parse_result(
        sha256="b1" * 32,
        content_uid="b1" * 32,
        status="EMPTY",
    )
    service = _checker(workspace, parse_results=[parse_result])
    report = service.check()
    assert report.issue_counts["REGISTRY_EMPTY_RESULT"] == 1


def test_tc019_skipped_result_aggregation(workspace: Path) -> None:
    parse_result = _parse_result(
        sha256="c1" * 32,
        content_uid="c1" * 32,
        status="SKIPPED",
    )
    service = _checker(workspace, parse_results=[parse_result])
    report = service.check()
    assert report.issue_counts["REGISTRY_SKIPPED_RESULT"] == 1
    issue = next(item for item in report.issues if item.issue_code == "REGISTRY_SKIPPED_RESULT")
    assert issue.severity == "INFO"


def test_tc020_empty_candidate_set(workspace: Path) -> None:
    service = _checker(workspace, candidates=[])
    report = service.check(sha256="missing" * 8)
    assert report.summary["checked_parse_result_count"] == 0
    assert report.summary["issue_count"] == 0
    assert report.report_path is not None
    assert report.report_path.is_file()


def test_tc033_report_schema(workspace: Path) -> None:
    service = _checker(workspace, candidates=[])
    report = service.check()
    payload = report.to_dict()
    expected_keys = {
        "report_type",
        "schema_version",
        "generated_at",
        "mode",
        "scope",
        "summary",
        "issue_counts",
        "by_parser",
        "by_status",
        "by_route_type",
        "by_severity",
        "issues",
        "recommendations",
    }
    assert expected_keys.issubset(payload.keys())
    assert set(payload["issue_counts"]) == set(ISSUE_CODES)


def test_tc028_no_db_write(workspace: Path) -> None:
    session = MagicMock()
    session.__enter__.return_value = session
    session.__exit__.return_value = None
    session.scalars.return_value.all.return_value = []
    factory = MagicMock(return_value=session)
    config = _test_config(workspace)
    service = ParseQualityCheckerService(config, session_factory=factory)
    service._load_candidates = lambda **kwargs: []  # type: ignore[method-assign]
    service.check()
    session.add.assert_not_called()
    session.delete.assert_not_called()
    session.merge.assert_not_called()
    session.commit.assert_not_called()


def test_tc029_no_parser_invocation(workspace: Path) -> None:
    service = _checker(workspace, candidates=[])
    with patch("app.services.markitdown_parser.MarkItDownParserService") as markitdown_mock:
        with patch("app.services.mineru_pdf_parser.MineruPdfParserService") as mineru_mock:
            with patch("subprocess.run", side_effect=AssertionError("subprocess must not run")):
                service.check()
    markitdown_mock.assert_not_called()
    mineru_mock.assert_not_called()


def test_tc032_only_report_file_written(workspace: Path) -> None:
    service = _checker(workspace, candidates=[])
    before = set(workspace.rglob("*"))
    report = service.check()
    after = set(workspace.rglob("*"))
    new_files = after - before
    assert len(new_files) == 1
    assert report.report_path in new_files


def test_cli_default_exit_code_zero(workspace: Path, tmp_path: Path) -> None:
    config_path = tmp_path / "app.yaml"
    config_path.write_text(
        f"""app:
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
""",
        encoding="utf-8",
    )
    fake_report = SimpleNamespace(
        summary={"issue_count": 0, "critical_count": 0, "error_count": 0, "warning_count": 0, "checked_parse_result_count": 0},
        report_path=workspace / "reports" / "parse_quality_report_test.json",
    )
    with patch.object(ParseQualityCheckerService, "check", return_value=fake_report):
        result = cli_runner.invoke(
            app,
            ["check-parse-quality", "--config", str(config_path)],
        )
    assert result.exit_code == 0


def test_cli_fail_on_issue_exit_code_two(workspace: Path, tmp_path: Path) -> None:
    config_path = tmp_path / "app.yaml"
    config_path.write_text(
        f"""app:
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
""",
        encoding="utf-8",
    )
    fake_report = SimpleNamespace(
        summary={"issue_count": 2, "critical_count": 0, "error_count": 2, "warning_count": 0, "checked_parse_result_count": 1},
        report_path=workspace / "reports" / "parse_quality_report_test.json",
    )
    with patch.object(ParseQualityCheckerService, "check", return_value=fake_report):
        result = cli_runner.invoke(
            app,
            ["check-parse-quality", "--config", str(config_path), "--fail-on-issue"],
        )
    assert result.exit_code == 2


def test_cli_invalid_parser_name(workspace: Path, tmp_path: Path) -> None:
    config_path = tmp_path / "app.yaml"
    config_path.write_text(
        f"""app:
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
""",
        encoding="utf-8",
    )
    result = cli_runner.invoke(
        app,
        ["check-parse-quality", "--config", str(config_path), "--parser-name", "magic-pdf"],
    )
    assert result.exit_code == 1


def _patch_path_is_dir(
    monkeypatch: pytest.MonkeyPatch,
    *,
    deny_paths: set[str],
    errno: int = 13,
) -> None:
    original_is_dir = Path.is_dir

    def patched_is_dir(self: Path) -> bool:
        if self.as_posix() in deny_paths:
            raise PermissionError(errno, "Permission denied", self.as_posix())
        return original_is_dir(self)

    monkeypatch.setattr(Path, "is_dir", patched_is_dir)


def _patch_path_is_file(
    monkeypatch: pytest.MonkeyPatch,
    *,
    deny_paths: set[str],
    errno: int = 13,
) -> None:
    original_is_file = Path.is_file

    def patched_is_file(self: Path) -> bool:
        if self.as_posix() in deny_paths:
            raise PermissionError(errno, "Permission denied", self.as_posix())
        return original_is_file(self)

    monkeypatch.setattr(Path, "is_file", patched_is_file)


def test_p5_parsed_dir_permission_denied_generates_report(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sha256 = "p5" * 32
    content_uid = sha256
    forbidden_dir = "/tmp/pytest-of-root/forbidden/parsed"
    parse_result = _parse_result(
        sha256=sha256,
        content_uid=content_uid,
        parsed_dir=forbidden_dir,
    )
    _patch_path_is_dir(monkeypatch, deny_paths={forbidden_dir})
    service = _checker(workspace, parse_results=[parse_result])
    report = service.check()
    assert report.report_path is not None
    assert report.report_path.is_file()
    issue = next(item for item in report.issues if item.issue_code == "MISSING_PARSED_DIR")
    assert issue.severity == "ERROR"
    assert issue.evidence["error"] == "PermissionError"
    assert issue.evidence["errno"] == 13
    assert issue.evidence["path"] == forbidden_dir
    assert set(report.issue_counts) == set(ISSUE_CODES)


def test_p5_parsed_text_permission_denied_generates_report(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sha256 = "p6" * 32
    content_uid = sha256
    parsed_dir = build_parsed_content_dir(workspace / "parsed", sha256)
    artifacts = build_parsed_artifact_paths(parsed_dir)
    parsed_dir.mkdir(parents=True)
    artifacts["parsed_metadata"].write_text("{}", encoding="utf-8")
    artifacts["parse_manifest"].write_text("{}", encoding="utf-8")
    parse_result = _parse_result(
        sha256=sha256,
        content_uid=content_uid,
        parsed_dir=parsed_dir.as_posix(),
        manifest_path=artifacts["parse_manifest"].as_posix(),
    )
    _patch_path_is_file(monkeypatch, deny_paths={artifacts["parsed_text"].as_posix()})
    service = _checker(workspace, parse_results=[parse_result])
    report = service.check()
    assert report.report_path is not None
    issue = next(item for item in report.issues if item.issue_code == "MISSING_PARSED_TEXT")
    assert issue.severity == "ERROR"
    assert issue.evidence["error"] == "PermissionError"
    assert issue.evidence["errno"] == 13
    assert issue.evidence["path"] == artifacts["parsed_text"].as_posix()
    assert set(report.issue_counts) == set(ISSUE_CODES)


def test_p5_parse_manifest_permission_denied_generates_report(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sha256 = "p7" * 32
    content_uid = sha256
    parsed_dir = build_parsed_content_dir(workspace / "parsed", sha256)
    artifacts = build_parsed_artifact_paths(parsed_dir)
    parsed_dir.mkdir(parents=True)
    artifacts["parsed_text"].write_text("x", encoding="utf-8")
    artifacts["parsed_metadata"].write_text("{}", encoding="utf-8")
    parse_result = _parse_result(
        sha256=sha256,
        content_uid=content_uid,
        parsed_dir=parsed_dir.as_posix(),
        manifest_path=artifacts["parse_manifest"].as_posix(),
    )
    _patch_path_is_file(monkeypatch, deny_paths={artifacts["parse_manifest"].as_posix()})
    service = _checker(workspace, parse_results=[parse_result])
    report = service.check()
    assert report.report_path is not None
    manifest_issues = [
        issue
        for issue in report.issues
        if issue.issue_code in ("MISSING_PARSE_MANIFEST", "INVALID_PARSE_MANIFEST_JSON")
    ]
    assert manifest_issues
    assert all(issue.severity == "ERROR" for issue in manifest_issues)
    assert any(issue.evidence.get("error") == "PermissionError" for issue in manifest_issues)
    assert set(report.issue_counts) == set(ISSUE_CODES)


def test_p5_issue_counts_include_all_eighteen_codes_on_permission_error(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sha256 = "p8" * 32
    content_uid = sha256
    forbidden_dir = "/tmp/pytest-of-root/forbidden/parsed2"
    parse_result = _parse_result(
        sha256=sha256,
        content_uid=content_uid,
        parsed_dir=forbidden_dir,
    )
    _patch_path_is_dir(monkeypatch, deny_paths={forbidden_dir})
    service = _checker(workspace, parse_results=[parse_result])
    report = service.check()
    assert set(report.issue_counts) == set(ISSUE_CODES)
    assert len(report.issue_counts) == len(ISSUE_CODES)
    assert all(isinstance(count, int) for count in report.issue_counts.values())
