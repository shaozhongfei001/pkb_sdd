from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = PROJECT_ROOT / "frontend"
if str(FRONTEND_ROOT) not in sys.path:
    sys.path.insert(0, str(FRONTEND_ROOT))

from app.core.config import AppConfig, MysqlConfig, RawConfig, StorageConfig
from app.models.parse_registry import KbParseRun
from app.schemas.search import SearchResponse, SearchQuery
from streamlit_admin.lib import repositories
from streamlit_admin.lib.config_loader import load_app_config, resolve_config_path
from streamlit_admin.lib.repositories import (
    _classify_report_name,
    list_quality_reports,
    read_curated_markdown,
)
from streamlit_admin.lib.safe_paths import PathTraversalError, resolve_under_root
from streamlit_admin.lib.search_client import search_kb


def _test_config(workspace_root: Path) -> AppConfig:
    return AppConfig(
        pipeline_version="v1.1",
        storage=StorageConfig(
            source_registry_root=workspace_root / "source_registry",
            raw_vault_root=workspace_root / "raw_vault",
            parsed_root=workspace_root / "parsed",
            curated_root=workspace_root / "curated",
            reports_root=workspace_root / "reports",
            quarantine_root=workspace_root / "quarantine",
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


# --- safe_paths ---


def test_resolve_under_root_accepts_relative_path(tmp_path: Path) -> None:
    root = tmp_path / "curated"
    root.mkdir()
    target = root / "projects" / "DEMO"
    target.mkdir(parents=True)
    (target / "card.md").write_text("# demo", encoding="utf-8")

    resolved = resolve_under_root(root, "projects/DEMO/card.md")
    assert resolved == (root / "projects" / "DEMO" / "card.md").resolve()
    assert resolved.read_text(encoding="utf-8") == "# demo"


def test_resolve_under_root_rejects_dotdot(tmp_path: Path) -> None:
    root = tmp_path / "curated"
    root.mkdir()
    with pytest.raises(PathTraversalError, match="traversal"):
        resolve_under_root(root, "../etc/passwd")


def test_resolve_under_root_rejects_absolute_path(tmp_path: Path) -> None:
    root = tmp_path / "curated"
    root.mkdir()
    with pytest.raises(PathTraversalError, match="absolute"):
        resolve_under_root(root, "/etc/passwd")


def test_resolve_under_root_rejects_symlink(tmp_path: Path) -> None:
    root = tmp_path / "curated"
    root.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("secret", encoding="utf-8")
    link = root / "escape.md"
    link.symlink_to(outside)
    with pytest.raises(PathTraversalError, match="symlink|escapes root"):
        resolve_under_root(root, "escape.md")


# --- reports glob ---


def test_reports_glob_only_allowed_filenames(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "parse_quality_report_20250101T120000Z.json").write_text("{}", encoding="utf-8")
    (reports / "parse_quality_summary_20250101T120000Z.md").write_text("# s", encoding="utf-8")
    (reports / "parse_quality_summary_20250101T120000Z.json").write_text("{}", encoding="utf-8")
    (reports / "random_notes.txt").write_text("x", encoding="utf-8")
    (reports / "parse_quality_report_evil.json.bak").write_text("{}", encoding="utf-8")

    assert _classify_report_name("parse_quality_report_20250101T120000Z.json") == "quality_report_json"
    assert _classify_report_name("not_allowed.txt") is None

    listed = list_quality_reports(reports)
    names = {r.name for r in listed}
    assert names == {
        "parse_quality_report_20250101T120000Z.json",
        "parse_quality_summary_20250101T120000Z.md",
        "parse_quality_summary_20250101T120000Z.json",
    }


# --- curated markdown via safe path ---


def test_curated_markdown_read_uses_safe_path(tmp_path: Path) -> None:
    curated = tmp_path / "curated"
    rel = Path("projects/DEMO/00_project_card.md")
    target = curated / rel
    target.parent.mkdir(parents=True)
    target.write_text("# 项目卡片", encoding="utf-8")

    config = _test_config(tmp_path)
    body = read_curated_markdown(config, str(rel).replace("\\", "/"))
    assert "项目卡片" in body

    with pytest.raises(PathTraversalError):
        read_curated_markdown(config, "../../outside.md")


# --- search_client delegates to SearchService ---


def test_search_client_calls_search_service_not_raw_sql() -> None:
    config = _test_config(Path("/tmp/pkb_test"))
    mock_response = SearchResponse(
        query=SearchQuery(text="测试", scope="all"),
        hits=[],
        total_count=0,
        returned_count=0,
        scopes_executed=["document"],
        duration_ms=1,
    )
    mock_service = MagicMock()
    mock_service.search.return_value = mock_response

    with patch(
        "streamlit_admin.lib.search_client.SearchService",
        return_value=mock_service,
    ) as mock_cls:
        result = search_kb(config, query="测试", scope="document", limit=5)

    mock_cls.assert_called_once()
    mock_service.search.assert_called_once()
    assert result is mock_response
    assert "MATCH" not in inspect.getsource(search_kb)


# --- repository SELECT-only ---


_WRITE_PATTERNS = (
    "session.add(",
    "session.commit(",
    "session.flush(",
    "INSERT",
    "UPDATE",
    "DELETE",
    "ALTER",
    "DROP",
    "CREATE TABLE",
    "TRUNCATE",
)


def test_repository_module_has_no_write_patterns() -> None:
    source = inspect.getsource(repositories)
    lowered = source.upper()
    for pattern in _WRITE_PATTERNS:
        assert pattern.upper() not in lowered or pattern == "UPDATE" and "UPDATED_AT" in source


def test_search_client_module_has_no_write_patterns() -> None:
    from streamlit_admin.lib import search_client

    source = inspect.getsource(search_client)
    for pattern in _WRITE_PATTERNS:
        assert pattern not in source


# --- config loader uses storage.* ---


def test_config_loader_uses_storage_roots(tmp_path: Path) -> None:
    config_yaml = tmp_path / "app.yaml"
    config_yaml.write_text(
        """
app:
  pipeline_version: v1.1
storage:
  source_registry_root: ./source_registry
  raw_vault_root: ./raw_vault
  parsed_root: ./parsed
  curated_root: ./curated
  quarantine_root: ./quarantine
  reports_root: ./reports
mysql:
  host: 127.0.0.1
  port: 3306
  database: personal_kb
  username: u
  password: p
  charset: utf8mb4
raw:
  original_files_readonly: true
  copy_unique_content_to_vault: true
""".strip(),
        encoding="utf-8",
    )
    config = load_app_config(config_yaml)
    assert config.storage.curated_root.name == "curated"
    assert config.storage.reports_root.name == "reports"
    assert resolve_config_path() is None or isinstance(resolve_config_path(), Path)


# --- parse registry uses KbParseRun ---


def test_parse_registry_uses_kb_parse_run_model() -> None:
    source = inspect.getsource(repositories.list_parse_runs)
    assert "KbParseRun" in source
    assert "kb_parse_job" not in source.lower()


# --- page modules import without DB writes ---


def test_page_modules_do_not_contain_db_writes() -> None:
    pages_dir = FRONTEND_ROOT / "streamlit_admin" / "pages"
    for page_file in pages_dir.glob("*.py"):
        if page_file.name.startswith("_"):
            continue
        source = page_file.read_text(encoding="utf-8")
        tree = ast.parse(source)
        joined = source
        for pattern in ("session.add(", "session.commit(", "session.flush("):
            assert pattern not in joined, f"{page_file.name} contains {pattern}"
        assert "create_db_engine" not in joined or "session_factory" in joined


def test_lib_modules_import_cleanly() -> None:
    import streamlit_admin.lib.config_loader  # noqa: F401
    import streamlit_admin.lib.db  # noqa: F401
    import streamlit_admin.lib.formatters  # noqa: F401
    import streamlit_admin.lib.repositories  # noqa: F401
    import streamlit_admin.lib.safe_paths  # noqa: F401
    import streamlit_admin.lib.search_client  # noqa: F401


def test_formatters_truncate() -> None:
    from streamlit_admin.lib.formatters import truncate_text

    assert truncate_text("short") == "short"
    assert truncate_text("x" * 250, max_len=200).endswith("…")
