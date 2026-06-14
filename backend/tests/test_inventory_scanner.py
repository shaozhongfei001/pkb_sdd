from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.core.config import load_settings
from app.core.database import get_session, init_engine
from app.core.ids import compute_file_sha256, normalize_source_path
from app.models.file import KbFileContent, KbFileInstance
from app.services.inventory_scanner import STATUS_DISCOVERED, InventoryScanner


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config" / "app.yaml"
FIXTURES_ROOT = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def settings():
    if not CONFIG_PATH.is_file():
        pytest.skip(f"Config not found: {CONFIG_PATH}")
    return load_settings(CONFIG_PATH)


@pytest.fixture(scope="session")
def mysql_available(settings):
    try:
        init_engine(settings)
        with get_session(settings) as session:
            session.scalar(select(func.count()).select_from(KbFileInstance))
    except Exception as exc:
        pytest.skip(f"MySQL not available: {exc}")


@pytest.fixture
def db_session(settings, mysql_available):
    with get_session(settings) as session:
        yield session


def _cleanup_scan_paths(session, *roots: Path) -> None:
    normalized_roots = [normalize_source_path(root.resolve()) for root in roots]
    instances = [
        item
        for item in session.scalars(select(KbFileInstance)).all()
        if any(item.source_path.startswith(root) for root in normalized_roots)
    ]
    content_uids = {item.content_uid for item in instances if item.content_uid}
    for item in instances:
        session.delete(item)
    session.flush()

    for content_uid in content_uids:
        remaining = session.scalar(
            select(func.count())
            .select_from(KbFileInstance)
            .where(KbFileInstance.content_uid == content_uid)
        )
        if remaining == 0:
            content = session.scalar(
                select(KbFileContent).where(KbFileContent.content_uid == content_uid)
            )
            if content is not None:
                session.delete(content)
    session.commit()


def _cleanup_pytest_temp_paths(session) -> None:
    """Remove rows created under pytest tmp_path prefixes."""
    prefixes = ("/tmp/pytest-of-", "/var/tmp/pytest-of-")
    instances = [
        item
        for item in session.scalars(select(KbFileInstance)).all()
        if item.source_path.startswith(prefixes)
    ]
    if not instances:
        return
    content_uids = {item.content_uid for item in instances if item.content_uid}
    for item in instances:
        session.delete(item)
    session.flush()
    for content_uid in content_uids:
        remaining = session.scalar(
            select(func.count())
            .select_from(KbFileInstance)
            .where(KbFileInstance.content_uid == content_uid)
        )
        if remaining == 0:
            content = session.scalar(
                select(KbFileContent).where(KbFileContent.content_uid == content_uid)
            )
            if content is not None:
                session.delete(content)
    session.commit()


@pytest.fixture(scope="session", autouse=True)
def _cleanup_pytest_session(settings, mysql_available):
    yield
    with get_session(settings) as db_session:
        _cleanup_pytest_temp_paths(db_session)


@pytest.fixture(autouse=True)
def _cleanup_after_test(db_session, tmp_path: Path, request):
    yield
    if request.node.get_closest_marker("no_db_cleanup"):
        return
    _cleanup_scan_paths(db_session, tmp_path)
    if request.node.name == "test_scan_project_fixtures":
        _cleanup_scan_paths(db_session, FIXTURES_ROOT)


@pytest.fixture
def scanner(settings, db_session):
    return InventoryScanner(db_session, settings)


def _snapshot(path: Path) -> dict:
    data = path.read_bytes()
    stat_result = path.stat()
    return {
        "path": str(path),
        "name": path.name,
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": stat_result.st_size,
        "mode": stat_result.st_mode,
    }


def test_scan_normal_files(scanner, db_session, tmp_path: Path):
    _cleanup_scan_paths(db_session, tmp_path)
    token = uuid.uuid4().hex
    (tmp_path / "a.txt").write_text(f"alpha-{token}", encoding="utf-8")
    (tmp_path / "b.txt").write_text(f"beta-{token}", encoding="utf-8")

    report = scanner.scan_directory(tmp_path)
    assert report.scanned_files == 2
    assert report.new_instances == 2
    assert report.new_contents == 2
    assert not report.errors

    instance_count = db_session.scalar(
        select(func.count())
        .select_from(KbFileInstance)
        .where(KbFileInstance.source_path.like(f"{normalize_source_path(tmp_path)}%"))
    )
    assert instance_count == 2


def test_scan_idempotent(scanner, db_session, tmp_path: Path):
    _cleanup_scan_paths(db_session, tmp_path)
    (tmp_path / "once.txt").write_text(f"same-{uuid.uuid4().hex}", encoding="utf-8")

    scanner.scan_directory(tmp_path)
    db_session.commit()
    prefix = normalize_source_path(tmp_path)
    first_count = db_session.scalar(
        select(func.count())
        .select_from(KbFileInstance)
        .where(KbFileInstance.source_path.like(f"{prefix}%"))
    )

    report = scanner.scan_directory(tmp_path)
    db_session.commit()
    second_count = db_session.scalar(
        select(func.count())
        .select_from(KbFileInstance)
        .where(KbFileInstance.source_path.like(f"{prefix}%"))
    )

    assert second_count == first_count
    assert report.new_instances == 0
    assert report.updated_instances == 1


def test_scan_chinese_path(scanner, db_session, tmp_path: Path):
    chinese_dir = tmp_path / "中文路径" / "银行项目"
    chinese_dir.mkdir(parents=True)
    doc = chinese_dir / "方案.txt"
    doc.write_text("示例方案内容", encoding="utf-8")
    _cleanup_scan_paths(db_session, tmp_path)

    report = scanner.scan_directory(tmp_path)
    assert report.scanned_files == 1
    assert not report.errors

    instance = db_session.scalar(
        select(KbFileInstance).where(KbFileInstance.file_name == "方案.txt")
    )
    assert instance is not None
    assert instance.status == STATUS_DISCOVERED
    assert "中文路径" in instance.source_path


def test_scan_duplicate_content(scanner, db_session, tmp_path: Path):
    _cleanup_scan_paths(db_session, tmp_path)
    payload = f"duplicate-content-{uuid.uuid4().hex}"
    (tmp_path / "方案.txt").write_text(payload, encoding="utf-8")
    (tmp_path / "方案副本.txt").write_text(payload, encoding="utf-8")

    report = scanner.scan_directory(tmp_path)
    assert report.scanned_files == 2
    assert report.new_contents == 1
    assert report.duplicate_instances == 1

    sha256 = compute_file_sha256(tmp_path / "方案.txt")
    content_row = db_session.scalar(select(KbFileContent).where(KbFileContent.sha256 == sha256))
    instances = [
        item
        for item in db_session.scalars(select(KbFileInstance)).all()
        if item.source_path.startswith(normalize_source_path(tmp_path))
    ]
    assert content_row is not None
    assert content_row.instance_count == 2
    assert len(instances) == 2
    assert sum(item.is_duplicate_instance for item in instances) == 1


def test_scan_single_file_error_continues(scanner, db_session, tmp_path: Path, monkeypatch):
    _cleanup_scan_paths(db_session, tmp_path)
    good = tmp_path / "good.txt"
    bad = tmp_path / "bad.txt"
    good.write_text("ok", encoding="utf-8")
    bad.write_text("secret", encoding="utf-8")

    original_hash = compute_file_sha256

    def flaky_hash(path: Path, chunk_size: int = 1024 * 1024) -> str:
        if path.name == "bad.txt":
            raise PermissionError("simulated read failure")
        return original_hash(path, chunk_size=chunk_size)

    monkeypatch.setattr("app.services.inventory_scanner.compute_file_sha256", flaky_hash)

    report = scanner.scan_directory(tmp_path)
    db_session.commit()

    assert report.scanned_files == 2
    assert len(report.errors) == 1
    good_instance = db_session.scalar(
        select(KbFileInstance).where(KbFileInstance.file_name == "good.txt")
    )
    assert good_instance is not None
    assert good_instance.status == STATUS_DISCOVERED


def test_original_files_unchanged(scanner, db_session, tmp_path: Path):
    _cleanup_scan_paths(db_session, tmp_path)
    doc = tmp_path / "protected.txt"
    doc.write_text("do-not-touch", encoding="utf-8")
    before = _snapshot(doc)

    scanner.scan_directory(tmp_path)
    after = _snapshot(doc)

    assert before == after


def test_scan_project_fixtures(scanner, db_session):
    if not FIXTURES_ROOT.is_dir():
        pytest.skip("fixtures directory missing")

    _cleanup_scan_paths(db_session, FIXTURES_ROOT)
    report = scanner.scan_directory(FIXTURES_ROOT)
    db_session.commit()

    assert report.scanned_files >= 2
    assert report.new_contents >= 1
    assert report.duplicate_instances >= 1
