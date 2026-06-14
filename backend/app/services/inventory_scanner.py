from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import AppConfig, ensure_readonly
from app.core.database import create_db_engine, create_session_factory
from app.core.file_types import guess_mime_type, is_document_candidate, should_skip_dir
from app.core.ids import compute_sha256, compute_source_path_hash, normalize_path
from app.models.file import KbFileContent, KbFileInstance

logger = logging.getLogger(__name__)

STATUS_DISCOVERED = "DISCOVERED"
STATUS_ERROR = "ERROR"
STATUS_CONTENT_REGISTERED = "CONTENT_REGISTERED"
VAULT_NOT_COPIED = "NOT_COPIED"


@dataclass
class ScanError:
    path: str
    message: str


@dataclass
class ScanResult:
    scan_root: str
    scanned_files: int = 0
    new_instances: int = 0
    updated_instances: int = 0
    new_contents: int = 0
    updated_contents: int = 0
    duplicate_instances: int = 0
    errors: list[ScanError] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "scan_root": self.scan_root,
            "scanned_files": self.scanned_files,
            "new_instances": self.new_instances,
            "updated_instances": self.updated_instances,
            "new_contents": self.new_contents,
            "updated_contents": self.updated_contents,
            "duplicate_instances": self.duplicate_instances,
            "errors": [{"path": item.path, "message": item.message} for item in self.errors],
        }


class InventoryScanner:
    def __init__(self, config: AppConfig) -> None:
        ensure_readonly(config)
        self.config = config
        engine = create_db_engine(config)
        self.session_factory = create_session_factory(engine)

    def scan(self, scan_root: Path, source_root: Path | None = None) -> ScanResult:
        normalized_root = normalize_path(scan_root)
        if not normalized_root.exists():
            raise FileNotFoundError(f"Scan path does not exist: {normalized_root}")

        effective_source_root = normalize_path(source_root or normalized_root)
        result = ScanResult(scan_root=normalized_root.as_posix())
        candidates = self._collect_candidates(normalized_root)

        for candidate in candidates:
            self._process_file(
                session_factory=self.session_factory,
                file_path=candidate,
                source_root=effective_source_root,
                result=result,
            )

        with self.session_factory() as session:
            result.duplicate_instances = self._count_duplicate_instances(
                session, normalized_root
            )

        self._write_report(result)
        return result

    def _collect_candidates(self, scan_root: Path) -> list[Path]:
        candidates: list[Path] = []
        for path in scan_root.rglob("*"):
            if any(should_skip_dir(part) for part in path.parts):
                continue
            if is_document_candidate(path):
                candidates.append(path)
        return sorted(candidates)

    def _process_file(
        self,
        session_factory: sessionmaker[Session],
        file_path: Path,
        source_root: Path,
        result: ScanResult,
    ) -> None:
        result.scanned_files += 1
        normalized_path = normalize_path(file_path)
        source_path_text = normalized_path.as_posix()

        try:
            stat = normalized_path.stat()
            sha256 = compute_sha256(normalized_path)
            source_path_hash = compute_source_path_hash(normalized_path)
            file_ext = normalized_path.suffix.lower() or None
            mime_type = guess_mime_type(normalized_path)
            modified_time = datetime.fromtimestamp(stat.st_mtime, tz=UTC).replace(tzinfo=None)
            created_time = datetime.fromtimestamp(stat.st_ctime, tz=UTC).replace(tzinfo=None)

            with session_factory() as session:
                content, content_created = self._upsert_content(
                    session=session,
                    sha256=sha256,
                    file_size=stat.st_size,
                    file_ext=file_ext,
                    mime_type=mime_type,
                )
                instance, instance_created = self._upsert_instance(
                    session=session,
                    source_path=source_path_text,
                    source_path_hash=source_path_hash,
                    file_name=normalized_path.name,
                    file_ext=file_ext,
                    file_size=stat.st_size,
                    mime_type=mime_type,
                    created_time=created_time,
                    modified_time=modified_time,
                    sha256=sha256,
                    source_root=source_root.as_posix(),
                )
                self._refresh_duplicate_state(session, sha256)
                instance_uid = instance.file_instance_uid
                content_uid = content.content_uid
                session.commit()

            if content_created:
                result.new_contents += 1
            else:
                result.updated_contents += 1
            if instance_created:
                result.new_instances += 1
            else:
                result.updated_instances += 1

            logger.info(
                "Scanned file path=%s sha256=%s instance_uid=%s content_uid=%s",
                source_path_text,
                sha256,
                instance_uid,
                content_uid,
            )
        except Exception as exc:
            logger.exception("Failed to scan file: %s", source_path_text)
            result.errors.append(ScanError(path=source_path_text, message=str(exc)))
            self._record_instance_error(
                session_factory=session_factory,
                source_path=source_path_text,
                source_root=source_root.as_posix(),
                message=str(exc),
            )

    def _upsert_content(
        self,
        session: Session,
        sha256: str,
        file_size: int,
        file_ext: str | None,
        mime_type: str | None,
    ) -> tuple[KbFileContent, bool]:
        content = session.scalar(
            select(KbFileContent).where(KbFileContent.sha256 == sha256)
        )
        if content is None:
            content = KbFileContent(
                content_uid=sha256,
                sha256=sha256,
                file_size=file_size,
                file_ext=file_ext,
                mime_type=mime_type,
                instance_count=0,
                vault_status=VAULT_NOT_COPIED,
                status=STATUS_CONTENT_REGISTERED,
            )
            session.add(content)
            session.flush()
            return content, True

        content.file_size = file_size
        content.file_ext = file_ext
        content.mime_type = mime_type
        return content, False

    def _upsert_instance(
        self,
        session: Session,
        source_path: str,
        source_path_hash: str,
        file_name: str,
        file_ext: str | None,
        file_size: int,
        mime_type: str | None,
        created_time: datetime,
        modified_time: datetime,
        sha256: str,
        source_root: str,
    ) -> tuple[KbFileInstance, bool]:
        instance = session.scalar(
            select(KbFileInstance).where(
                KbFileInstance.source_path_hash == source_path_hash
            )
        )
        if instance is None:
            instance = KbFileInstance(
                file_instance_uid=source_path_hash,
                source_path=source_path,
                source_path_hash=source_path_hash,
                file_name=file_name,
                file_ext=file_ext,
                file_size=file_size,
                mime_type=mime_type,
                created_time=created_time,
                modified_time=modified_time,
                content_uid=sha256,
                sha256=sha256,
                source_root=source_root,
                is_available=1,
                is_duplicate_instance=0,
                status=STATUS_DISCOVERED,
                error_message=None,
            )
            session.add(instance)
            session.flush()
            return instance, True

        instance.source_path = source_path
        instance.file_name = file_name
        instance.file_ext = file_ext
        instance.file_size = file_size
        instance.mime_type = mime_type
        instance.created_time = created_time
        instance.modified_time = modified_time
        instance.content_uid = sha256
        instance.sha256 = sha256
        instance.source_root = source_root
        instance.is_available = 1
        instance.status = STATUS_DISCOVERED
        instance.error_message = None
        return instance, False

    def _refresh_duplicate_state(self, session: Session, sha256: str) -> None:
        instances = session.scalars(
            select(KbFileInstance)
            .where(KbFileInstance.sha256 == sha256, KbFileInstance.status == STATUS_DISCOVERED)
            .order_by(KbFileInstance.created_at.asc(), KbFileInstance.id.asc())
        ).all()
        if not instances:
            return

        master = instances[0]
        for index, instance in enumerate(instances):
            instance.is_duplicate_instance = 0 if index == 0 else 1

        content = session.scalar(
            select(KbFileContent).where(KbFileContent.sha256 == sha256)
        )
        if content is not None:
            content.master_file_instance_uid = master.file_instance_uid
            content.instance_count = len(instances)

    def _record_instance_error(
        self,
        session_factory: sessionmaker[Session],
        source_path: str,
        source_root: str,
        message: str,
    ) -> None:
        try:
            path = Path(source_path)
            source_path_hash = compute_source_path_hash(path)
            with session_factory() as session:
                instance = session.scalar(
                    select(KbFileInstance).where(
                        KbFileInstance.source_path_hash == source_path_hash
                    )
                )
                if instance is None:
                    instance = KbFileInstance(
                        file_instance_uid=source_path_hash,
                        source_path=source_path,
                        source_path_hash=source_path_hash,
                        file_name=path.name,
                        file_ext=path.suffix.lower() or None,
                        source_root=source_root,
                        is_available=0,
                        is_duplicate_instance=0,
                        status=STATUS_ERROR,
                        error_message=message,
                    )
                    session.add(instance)
                else:
                    instance.status = STATUS_ERROR
                    instance.error_message = message
                    instance.is_available = 0
                session.commit()
        except Exception:
            logger.exception("Failed to record scan error for path=%s", source_path)

    def _count_duplicate_instances(self, session: Session, scan_root: Path) -> int:
        prefix = scan_root.as_posix()
        rows = session.scalars(
            select(KbFileInstance).where(
                KbFileInstance.source_path.like(f"{prefix}%"),
                KbFileInstance.is_duplicate_instance == 1,
            )
        ).all()
        return len(rows)

    def _write_report(self, result: ScanResult) -> None:
        reports_root = self.config.storage.reports_root
        reports_root.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        report_path = reports_root / f"inventory_scan_{timestamp}.json"
        report_path.write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        logger.info("Wrote inventory scan report: %s", report_path)
