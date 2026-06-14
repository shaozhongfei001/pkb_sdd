from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import AppSettings
from app.core.file_types import guess_mime_type, is_candidate_file, should_skip_dir
from app.core.ids import (
    compute_file_sha256,
    compute_source_path_hash,
    make_content_uid,
    make_file_instance_uid,
    normalize_source_path,
)
from app.models.file import KbFileContent, KbFileInstance

logger = logging.getLogger(__name__)

STATUS_DISCOVERED = "DISCOVERED"
STATUS_ERROR = "ERROR"
STATUS_CONTENT_REGISTERED = "CONTENT_REGISTERED"


@dataclass
class ScanError:
    path: str
    message: str


@dataclass
class ScanReport:
    scanned_files: int = 0
    new_instances: int = 0
    updated_instances: int = 0
    new_contents: int = 0
    updated_contents: int = 0
    duplicate_instances: int = 0
    errors: list[ScanError] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "scanned_files": self.scanned_files,
            "new_instances": self.new_instances,
            "updated_instances": self.updated_instances,
            "new_contents": self.new_contents,
            "updated_contents": self.updated_contents,
            "duplicate_instances": self.duplicate_instances,
            "errors": [{"path": item.path, "message": item.message} for item in self.errors],
        }


class InventoryScanner:
    def __init__(self, session: Session, settings: AppSettings):
        self.session = session
        self.settings = settings

    def scan_directory(self, scan_path: Path, source_root: Path | None = None) -> ScanReport:
        root = scan_path.resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"Scan path is not a directory: {root}")

        self.settings.ensure_readonly()
        source_root_resolved = (source_root or root).resolve()
        report = ScanReport()

        for file_path in self._iter_candidate_files(root):
            report.scanned_files += 1
            try:
                self._process_file(file_path, source_root_resolved, report)
                self.session.commit()
            except Exception as exc:
                self.session.rollback()
                message = str(exc)
                logger.exception("Failed to scan %s", file_path)
                report.errors.append(ScanError(path=str(file_path), message=message))
                self._record_error_instance(file_path, source_root_resolved, message)
                self.session.commit()

        report.duplicate_instances = self._count_duplicate_instances(root)
        self._write_report(report, root)
        return report

    def _iter_candidate_files(self, root: Path):
        for path in sorted(root.rglob("*")):
            if path.is_dir():
                continue
            if any(should_skip_dir(part) for part in path.relative_to(root).parts):
                continue
            if is_candidate_file(path):
                yield path

    def _process_file(self, file_path: Path, source_root: Path, report: ScanReport) -> None:
        normalized = normalize_source_path(file_path)
        source_path_hash = compute_source_path_hash(normalized)
        sha256 = compute_file_sha256(file_path)
        stat = file_path.stat()
        file_ext = file_path.suffix.lower() or None
        mime_type = guess_mime_type(file_path)
        content_uid = make_content_uid(sha256)
        file_instance_uid = make_file_instance_uid(source_path_hash)

        content = self.session.scalar(
            select(KbFileContent).where(KbFileContent.sha256 == sha256)
        )
        if content is None:
            content = KbFileContent(
                content_uid=content_uid,
                sha256=sha256,
                file_size=stat.st_size,
                file_ext=file_ext,
                mime_type=mime_type,
                status=STATUS_CONTENT_REGISTERED,
            )
            self.session.add(content)
            report.new_contents += 1
        else:
            content.file_size = stat.st_size
            content.file_ext = file_ext
            content.mime_type = mime_type
            report.updated_contents += 1

        instance = self.session.scalar(
            select(KbFileInstance).where(KbFileInstance.source_path_hash == source_path_hash)
        )
        if instance is None:
            instance = KbFileInstance(
                file_instance_uid=file_instance_uid,
                source_path=normalized,
                source_path_hash=source_path_hash,
                file_name=file_path.name,
            )
            self.session.add(instance)
            report.new_instances += 1
        else:
            report.updated_instances += 1

        instance.source_path = normalized
        instance.file_name = file_path.name
        instance.file_ext = file_ext
        instance.file_size = stat.st_size
        instance.mime_type = mime_type
        instance.created_time = self._stat_time(stat.st_ctime)
        instance.modified_time = self._stat_time(stat.st_mtime)
        instance.content_uid = content_uid
        instance.sha256 = sha256
        instance.source_root = normalize_source_path(source_root)
        instance.is_available = 1
        instance.status = STATUS_DISCOVERED
        instance.error_message = None
        instance.metadata_json = {"scan_root": normalize_source_path(source_root)}

        self.session.flush()
        self._refresh_content_links(content)

    def _count_duplicate_instances(self, scan_root: Path) -> int:
        prefix = normalize_source_path(scan_root)
        count = self.session.scalar(
            select(func.count())
            .select_from(KbFileInstance)
            .where(
                KbFileInstance.source_path.like(f"{prefix}%"),
                KbFileInstance.is_duplicate_instance == 1,
            )
        )
        return int(count or 0)

    def _refresh_content_links(self, content: KbFileContent) -> None:
        instances = list(
            self.session.scalars(
                select(KbFileInstance)
                .where(
                    KbFileInstance.content_uid == content.content_uid,
                    KbFileInstance.status == STATUS_DISCOVERED,
                )
                .order_by(KbFileInstance.id.asc())
            )
        )
        content.instance_count = len(instances)
        if not instances:
            return

        master_uid = content.master_file_instance_uid
        master = next((item for item in instances if item.file_instance_uid == master_uid), None)
        if master is None:
            master = instances[0]
            content.master_file_instance_uid = master.file_instance_uid

        for instance in instances:
            is_duplicate = instance.file_instance_uid != content.master_file_instance_uid
            instance.is_duplicate_instance = 1 if is_duplicate else 0

    def _record_error_instance(
        self,
        file_path: Path,
        source_root: Path,
        message: str,
    ) -> None:
        normalized = normalize_source_path(file_path)
        source_path_hash = compute_source_path_hash(normalized)
        file_instance_uid = make_file_instance_uid(source_path_hash)
        file_ext = file_path.suffix.lower() or None

        instance = self.session.scalar(
            select(KbFileInstance).where(KbFileInstance.source_path_hash == source_path_hash)
        )
        if instance is None:
            instance = KbFileInstance(
                file_instance_uid=file_instance_uid,
                source_path=normalized,
                source_path_hash=source_path_hash,
                file_name=file_path.name,
            )
            self.session.add(instance)

        instance.file_ext = file_ext
        instance.source_root = normalize_source_path(source_root)
        instance.is_available = 0
        instance.status = STATUS_ERROR
        instance.error_message = message[:2000]

    def _write_report(self, report: ScanReport, scan_root: Path) -> None:
        reports_root = self.settings.storage.reports_root
        reports_root.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        report_path = reports_root / f"inventory_scan_{timestamp}.json"
        payload = {"scan_root": normalize_source_path(scan_root), **report.to_dict()}
        report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Wrote inventory scan report to %s", report_path)

    @staticmethod
    def _stat_time(epoch: float) -> datetime:
        return datetime.fromtimestamp(epoch, tz=timezone.utc).replace(tzinfo=None)
