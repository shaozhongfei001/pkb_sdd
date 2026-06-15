from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import AppConfig, ensure_readonly
from app.core.database import create_db_engine, create_session_factory
from app.core.ids import compute_sha256
from app.core.parsed_paths import build_parsed_artifact_paths, build_parsed_content_dir
from app.models.document import KbDocument
from app.models.file import KbFileContent
from app.models.parse_registry import KbParseResult, KbParsedArtifact, KbParseRun

logger = logging.getLogger(__name__)

PARSE_REGISTRY_MAX_LIMIT = 100
PARSER_PROFILE_MARKITDOWN = "markitdown_default_v1"

RUN_STATUS_PENDING = "PENDING"
RUN_STATUS_RUNNING = "RUNNING"
RUN_STATUS_COMPLETED = "COMPLETED"
RUN_STATUS_PARTIAL = "PARTIAL"
RUN_STATUS_FAILED = "FAILED"

RESULT_STATUS_SUCCESS = "SUCCESS"
RESULT_STATUS_EMPTY = "EMPTY"
RESULT_STATUS_SKIPPED = "SKIPPED"
RESULT_STATUS_FAILED = "FAILED"

ARTIFACT_TYPE_PARSED_TEXT = "PARSED_TEXT"
ARTIFACT_TYPE_PARSED_METADATA = "PARSED_METADATA"
ARTIFACT_TYPE_PARSE_MANIFEST = "PARSE_MANIFEST"
ARTIFACT_TYPE_PARSE_REPORT = "PARSE_REPORT"

ARTIFACT_STATUS_INDEXED = "INDEXED"
ARTIFACT_STATUS_MISSING = "MISSING"

TRIGGER_REGISTER_REPORT = "REGISTER_REPORT"
TRIGGER_RECONCILE = "RECONCILE"

ERROR_INVALID_DRY_RUN_REPORT = "INVALID_DRY_RUN_REPORT"
ERROR_INVALID_REPORT = "INVALID_REPORT"
ERROR_MISSING_MANIFEST = "MISSING_MANIFEST"
ERROR_INVALID_MANIFEST = "INVALID_MANIFEST"
ERROR_UNKNOWN_CONTENT = "UNKNOWN_CONTENT"

PARSE_STATUS_PARSED = "PARSED"
PARSE_STATUS_PARSED_EMPTY = "PARSED_EMPTY"
PARSE_STATUS_PARSE_FAILED = "PARSE_FAILED"

DOCUMENT_PARSE_STATUS_PARSED = "PARSED"
DOCUMENT_PARSE_STATUS_PARSED_EMPTY = "PARSED_EMPTY"

RUN_UID_PATTERN = re.compile(r"^parse_run_\d{8}T\d{6}Z_[0-9a-f]{8}$")


class ParseRegistryError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class RegistryErrorEntry:
    content_uid: str
    sha256: str
    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "content_uid": self.content_uid,
            "sha256": self.sha256,
            "code": self.code,
            "message": self.message,
        }


@dataclass
class RegisterReportResult:
    run_uid: str | None = None
    status: str | None = None
    dry_run: bool = False
    total_candidates: int = 0
    in_scope_candidates: int = 0
    parsed_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    empty_count: int = 0
    results_recorded: int = 0
    artifacts_recorded: int = 0
    errors: list[RegistryErrorEntry] = field(default_factory=list)
    registry_report_path: Path | None = None
    preview: dict[str, Any] | None = None


@dataclass
class ReconcileResult:
    run_uid: str | None = None
    dry_run: bool = False
    manifests_scanned: int = 0
    results_recorded: int = 0
    artifacts_recorded: int = 0
    errors: list[RegistryErrorEntry] = field(default_factory=list)
    preview: dict[str, Any] | None = None


def generate_run_uid(now: datetime | None = None) -> str:
    ts = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    return f"parse_run_{ts}_{uuid.uuid4().hex[:8]}"


def generate_result_uid() -> str:
    return f"parse_result_{uuid.uuid4().hex[:16]}"


def generate_artifact_uid() -> str:
    return f"parsed_artifact_{uuid.uuid4().hex[:16]}"


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _load_report(report_path: Path) -> dict[str, Any]:
    if not report_path.is_file():
        raise ParseRegistryError(
            ERROR_INVALID_REPORT,
            f"Report not found: {report_path}",
        )
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ParseRegistryError(
            ERROR_INVALID_REPORT,
            f"Invalid report JSON: {exc}",
        ) from exc
    if not isinstance(payload, dict):
        raise ParseRegistryError(ERROR_INVALID_REPORT, "Report root must be a JSON object")
    return payload


def _load_manifest(manifest_path: Path) -> dict[str, Any] | None:
    if not manifest_path.is_file():
        return None
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _artifact_file_info(path: Path) -> tuple[str | None, int | None]:
    if not path.is_file():
        return None, None
    return compute_sha256(path), path.stat().st_size


class ParseRegistryService:
    def __init__(self, config: AppConfig) -> None:
        ensure_readonly(config)
        self.config = config
        engine = create_db_engine(config)
        self.session_factory = create_session_factory(engine)

    def register_parse_report(
        self,
        *,
        report_path: Path,
        dry_run: bool = False,
    ) -> RegisterReportResult:
        report_path = report_path.resolve()
        report = _load_report(report_path)

        if report.get("dry_run") is True:
            raise ParseRegistryError(
                ERROR_INVALID_DRY_RUN_REPORT,
                "Cannot ingest parse report with dry_run=true",
            )

        summary = report.get("summary") or {}
        parser_name = str(report.get("parser_name", "markitdown"))
        parser_adapter_version = str(report.get("parser_adapter_version", "005_mvp_v1"))
        filters = report.get("filters") or {}
        items = report.get("items") or []

        if dry_run:
            preview = self._build_register_preview(
                report_path=report_path,
                report=report,
                parser_name=parser_name,
                parser_adapter_version=parser_adapter_version,
                items=items,
            )
            registry_report_path = self._write_registry_report(
                {
                    "report_type": "registry_report",
                    "mode": "dry_run_preview",
                    "source_report_path": report_path.as_posix(),
                    "preview": preview,
                }
            )
            return RegisterReportResult(
                dry_run=True,
                total_candidates=int(summary.get("total_candidates", 0)),
                in_scope_candidates=int(summary.get("in_scope_candidates", 0)),
                parsed_count=int(summary.get("parsed_count", 0)),
                skipped_count=int(summary.get("skipped_count", 0)),
                failed_count=int(summary.get("failed_count", 0)),
                empty_count=int(summary.get("empty_count", 0)),
                preview=preview,
                registry_report_path=registry_report_path,
            )

        result = RegisterReportResult(dry_run=False)
        result.total_candidates = int(summary.get("total_candidates", 0))
        result.in_scope_candidates = int(summary.get("in_scope_candidates", 0))
        result.parsed_count = int(summary.get("parsed_count", 0))
        result.skipped_count = int(summary.get("skipped_count", 0))
        result.failed_count = int(summary.get("failed_count", 0))
        result.empty_count = int(summary.get("empty_count", 0))

        with self.session_factory() as session:
            run = self._get_or_create_run_for_report(
                session=session,
                report_path=report_path,
                parser_name=parser_name,
                parser_adapter_version=parser_adapter_version,
                filters=filters,
                summary=summary,
            )
            session.commit()
            result.run_uid = run.run_uid

            run = self.create_parse_run(
                session=session,
                run=run,
                status=RUN_STATUS_RUNNING,
                started_at=_utc_now(),
            )
            session.commit()

            for item in items:
                if not isinstance(item, dict):
                    continue
                try:
                    with session.begin():
                        recorded = self._ingest_report_item(
                            session=session,
                            run=run,
                            item=item,
                            parser_name=parser_name,
                            parser_adapter_version=parser_adapter_version,
                            report_path=report_path,
                        )
                        result.results_recorded += 1
                        result.artifacts_recorded += recorded["artifacts"]
                except Exception as exc:
                    session.rollback()
                    logger.exception("Failed to ingest report item")
                    content_uid = str(item.get("content_uid", ""))
                    sha256 = str(item.get("sha256", ""))
                    result.errors.append(
                        RegistryErrorEntry(
                            content_uid=content_uid,
                            sha256=sha256,
                            code="DB_ERROR",
                            message=str(exc),
                        )
                    )

            try:
                with session.begin():
                    self.record_parsed_artifact(
                        session=session,
                        run_uid=run.run_uid,
                        content_uid="",
                        sha256=None,
                        artifact_type=ARTIFACT_TYPE_PARSE_REPORT,
                        artifact_path=report_path.as_posix(),
                        parser_name=parser_name,
                        parser_adapter_version=parser_adapter_version,
                    )
                    result.artifacts_recorded += 1
            except Exception as exc:
                session.rollback()
                result.errors.append(
                    RegistryErrorEntry(
                        content_uid="",
                        sha256="",
                        code="DB_ERROR",
                        message=f"Failed to index parse report artifact: {exc}",
                    )
                )

            final_status = RUN_STATUS_PARTIAL if result.errors else RUN_STATUS_COMPLETED
            if result.failed_count > 0 and not result.errors:
                final_status = RUN_STATUS_PARTIAL

            registry_report_path = self._write_registry_report(
                {
                    "report_type": "registry_report",
                    "mode": "register",
                    "run_uid": run.run_uid,
                    "source_report_path": report_path.as_posix(),
                    "results_recorded": result.results_recorded,
                    "artifacts_recorded": result.artifacts_recorded,
                    "errors": [error.to_dict() for error in result.errors],
                }
            )

            self.finish_parse_run(
                session=session,
                run=run,
                status=final_status,
                registry_report_path=registry_report_path.as_posix(),
                finished_at=_utc_now(),
            )
            session.commit()
            result.status = final_status
            result.registry_report_path = registry_report_path

        return result

    def reconcile_parsed_artifacts(
        self,
        *,
        sha256: str | None = None,
        content_uid: str | None = None,
        limit: int | None = None,
        dry_run: bool = False,
    ) -> ReconcileResult:
        if not sha256 and not content_uid and limit is None:
            raise ParseRegistryError(
                "MISSING_FILTER",
                "Must provide at least one of --sha256, --content-uid, or --limit",
            )
        if limit is not None and limit > PARSE_REGISTRY_MAX_LIMIT:
            raise ParseRegistryError(
                "LIMIT_EXCEEDED",
                f"--limit must be <= {PARSE_REGISTRY_MAX_LIMIT}",
            )

        target_sha = sha256 or content_uid
        manifests = self._discover_manifests(target_sha=target_sha, limit=limit)

        if dry_run:
            preview = {
                "manifests_found": len(manifests),
                "manifest_paths": [path.as_posix() for path in manifests],
            }
            return ReconcileResult(
                dry_run=True,
                manifests_scanned=len(manifests),
                preview=preview,
            )

        result = ReconcileResult(dry_run=False, manifests_scanned=len(manifests))
        parser_name = "markitdown"
        parser_adapter_version = "005_mvp_v1"

        with self.session_factory() as session:
            run = self._get_or_create_reconcile_run(
                session=session,
                sha256=sha256,
                content_uid=content_uid,
                limit=limit,
                manifest_count=len(manifests),
                parser_name=parser_name,
                parser_adapter_version=parser_adapter_version,
            )
            session.commit()
            result.run_uid = run.run_uid

            run = self.create_parse_run(
                session=session,
                run=run,
                status=RUN_STATUS_RUNNING,
                started_at=_utc_now(),
            )
            session.commit()

            for manifest_path in manifests:
                try:
                    with session.begin():
                        recorded = self._ingest_manifest_path(
                            session=session,
                            run=run,
                            manifest_path=manifest_path,
                            parser_name=parser_name,
                            parser_adapter_version=parser_adapter_version,
                        )
                        if recorded:
                            result.results_recorded += 1
                            result.artifacts_recorded += recorded["artifacts"]
                except Exception as exc:
                    session.rollback()
                    logger.exception("Reconcile failed for manifest %s", manifest_path)
                    result.errors.append(
                        RegistryErrorEntry(
                            content_uid="",
                            sha256="",
                            code="DB_ERROR",
                            message=f"{manifest_path}: {exc}",
                        )
                    )

            final_status = RUN_STATUS_PARTIAL if result.errors else RUN_STATUS_COMPLETED
            self.finish_parse_run(
                session=session,
                run=run,
                status=final_status,
                finished_at=_utc_now(),
            )
            session.commit()

        return result

    def create_parse_run(
        self,
        *,
        session: Session,
        run: KbParseRun,
        status: str,
        started_at: datetime | None = None,
    ) -> KbParseRun:
        run.status = status
        if started_at is not None:
            run.started_at = started_at
        elif status == RUN_STATUS_RUNNING and run.started_at is None:
            run.started_at = _utc_now()
        session.add(run)
        session.flush()
        return run

    def finish_parse_run(
        self,
        *,
        session: Session,
        run: KbParseRun,
        status: str,
        finished_at: datetime | None = None,
        registry_report_path: str | None = None,
    ) -> KbParseRun:
        run.status = status
        run.finished_at = finished_at or _utc_now()
        if registry_report_path is not None:
            run.registry_report_path = registry_report_path
        session.add(run)
        session.flush()
        return run

    def fail_parse_run(
        self,
        *,
        session: Session,
        run: KbParseRun,
        error_message: str,
        finished_at: datetime | None = None,
    ) -> KbParseRun:
        run.status = RUN_STATUS_FAILED
        run.error_message = error_message
        run.finished_at = finished_at or _utc_now()
        session.add(run)
        session.flush()
        return run

    def record_parse_result(
        self,
        *,
        session: Session,
        run_uid: str,
        content_uid: str,
        sha256: str,
        status: str,
        parser_name: str,
        parser_adapter_version: str,
        route_type: str | None = None,
        decision: str | None = None,
        source_vault_path: str | None = None,
        parsed_dir: str | None = None,
        manifest_path: str | None = None,
        metadata_path: str | None = None,
        text_path: str | None = None,
        output_hash: str | None = None,
        output_size_bytes: int | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> KbParseResult:
        existing = session.scalar(
            select(KbParseResult).where(
                KbParseResult.run_uid == run_uid,
                KbParseResult.content_uid == content_uid,
                KbParseResult.parser_adapter_version == parser_adapter_version,
            )
        )

        retry_of_id: int | None = None
        if existing is None:
            previous_failed = session.scalar(
                select(KbParseResult)
                .where(
                    KbParseResult.content_uid == content_uid,
                    KbParseResult.parser_adapter_version == parser_adapter_version,
                    KbParseResult.status == RESULT_STATUS_FAILED,
                )
                .order_by(KbParseResult.id.desc())
                .limit(1)
            )
            if previous_failed is not None:
                retry_of_id = previous_failed.id

        if existing is None:
            result = KbParseResult(
                result_uid=generate_result_uid(),
                run_uid=run_uid,
                content_uid=content_uid,
                sha256=sha256,
                route_type=route_type,
                decision=decision,
                status=status,
                source_vault_path=source_vault_path,
                parsed_dir=parsed_dir,
                manifest_path=manifest_path,
                metadata_path=metadata_path,
                text_path=text_path,
                output_hash=output_hash,
                output_size_bytes=output_size_bytes,
                error_code=error_code,
                error_message=error_message,
                retry_of_result_id=retry_of_id,
                parser_name=parser_name,
                parser_adapter_version=parser_adapter_version,
                pipeline_version=self.config.pipeline_version,
                metadata_json=metadata,
            )
        else:
            result = existing
            result.sha256 = sha256
            result.route_type = route_type
            result.decision = decision
            result.status = status
            result.source_vault_path = source_vault_path
            result.parsed_dir = parsed_dir
            result.manifest_path = manifest_path
            result.metadata_path = metadata_path
            result.text_path = text_path
            result.output_hash = output_hash
            result.output_size_bytes = output_size_bytes
            result.error_code = error_code
            result.error_message = error_message
            result.parser_name = parser_name
            result.metadata_json = metadata
            if retry_of_id is not None and result.retry_of_result_id is None:
                result.retry_of_result_id = retry_of_id

        session.add(result)
        session.flush()
        return result

    def record_parsed_artifact(
        self,
        *,
        session: Session,
        run_uid: str,
        content_uid: str,
        sha256: str | None,
        artifact_type: str,
        artifact_path: str,
        parser_name: str,
        parser_adapter_version: str,
        status: str = ARTIFACT_STATUS_INDEXED,
        metadata: dict[str, Any] | None = None,
    ) -> KbParsedArtifact:
        path = Path(artifact_path)
        artifact_hash, artifact_size = _artifact_file_info(path)
        if not path.is_file():
            status = ARTIFACT_STATUS_MISSING

        existing = session.scalar(
            select(KbParsedArtifact).where(
                KbParsedArtifact.run_uid == run_uid,
                KbParsedArtifact.content_uid == content_uid,
                KbParsedArtifact.artifact_type == artifact_type,
                KbParsedArtifact.parser_name == parser_name,
                KbParsedArtifact.parser_adapter_version == parser_adapter_version,
            )
        )

        if existing is None:
            artifact = KbParsedArtifact(
                artifact_uid=generate_artifact_uid(),
                run_uid=run_uid,
                content_uid=content_uid,
                sha256=sha256,
                artifact_type=artifact_type,
                artifact_path=artifact_path,
                artifact_hash=artifact_hash,
                artifact_size_bytes=artifact_size,
                parser_name=parser_name,
                parser_adapter_version=parser_adapter_version,
                status=status,
                metadata_json=metadata,
            )
        else:
            artifact = existing
            artifact.sha256 = sha256
            artifact.artifact_path = artifact_path
            artifact.artifact_hash = artifact_hash
            artifact.artifact_size_bytes = artifact_size
            artifact.status = status
            artifact.metadata_json = metadata

        session.add(artifact)
        session.flush()
        return artifact

    def list_parse_runs(
        self,
        *,
        limit: int = 50,
        status: str | None = None,
        parser_name: str | None = None,
    ) -> list[KbParseRun]:
        with self.session_factory() as session:
            query = select(KbParseRun).order_by(KbParseRun.created_at.desc()).limit(limit)
            if status:
                query = query.where(KbParseRun.status == status)
            if parser_name:
                query = query.where(KbParseRun.parser_name == parser_name)
            return list(session.scalars(query).all())

    def get_parse_run(self, run_uid: str) -> KbParseRun | None:
        with self.session_factory() as session:
            return session.scalar(select(KbParseRun).where(KbParseRun.run_uid == run_uid))

    def list_parse_results(
        self,
        *,
        run_uid: str | None = None,
        content_uid: str | None = None,
        sha256: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[KbParseResult]:
        with self.session_factory() as session:
            query = select(KbParseResult).order_by(KbParseResult.id.desc()).limit(limit)
            if run_uid:
                query = query.where(KbParseResult.run_uid == run_uid)
            if content_uid:
                query = query.where(KbParseResult.content_uid == content_uid)
            if sha256:
                query = query.where(KbParseResult.sha256 == sha256)
            if status:
                query = query.where(KbParseResult.status == status)
            return list(session.scalars(query).all())

    def list_parsed_artifacts(
        self,
        *,
        content_uid: str | None = None,
        sha256: str | None = None,
        artifact_type: str | None = None,
        limit: int = 50,
    ) -> list[KbParsedArtifact]:
        with self.session_factory() as session:
            query = select(KbParsedArtifact).order_by(KbParsedArtifact.id.desc()).limit(limit)
            if content_uid:
                query = query.where(KbParsedArtifact.content_uid == content_uid)
            if sha256:
                query = query.where(KbParsedArtifact.sha256 == sha256)
            if artifact_type:
                query = query.where(KbParsedArtifact.artifact_type == artifact_type)
            return list(session.scalars(query).all())

    def _get_or_create_run_for_report(
        self,
        *,
        session: Session,
        report_path: Path,
        parser_name: str,
        parser_adapter_version: str,
        filters: dict[str, Any],
        summary: dict[str, Any],
    ) -> KbParseRun:
        report_path_str = report_path.as_posix()
        existing = session.scalar(
            select(KbParseRun).where(
                KbParseRun.report_path == report_path_str,
                KbParseRun.parser_adapter_version == parser_adapter_version,
            )
        )
        if existing is not None:
            existing.total_candidates = int(summary.get("total_candidates", 0))
            existing.in_scope_candidates = int(summary.get("in_scope_candidates", 0))
            existing.parsed_count = int(summary.get("parsed_count", 0))
            existing.skipped_count = int(summary.get("skipped_count", 0))
            existing.failed_count = int(summary.get("failed_count", 0))
            existing.empty_count = int(summary.get("empty_count", 0))
            existing.filters_json = filters
            session.add(existing)
            session.flush()
            return existing

        run = KbParseRun(
            run_uid=generate_run_uid(),
            parser_name=parser_name,
            parser_adapter_version=parser_adapter_version,
            parser_family="MARKITDOWN_FAMILY",
            trigger_type=TRIGGER_REGISTER_REPORT,
            filters_json=filters,
            status=RUN_STATUS_PENDING,
            dry_run=0,
            total_candidates=int(summary.get("total_candidates", 0)),
            in_scope_candidates=int(summary.get("in_scope_candidates", 0)),
            parsed_count=int(summary.get("parsed_count", 0)),
            skipped_count=int(summary.get("skipped_count", 0)),
            failed_count=int(summary.get("failed_count", 0)),
            empty_count=int(summary.get("empty_count", 0)),
            report_path=report_path_str,
        )
        session.add(run)
        session.flush()
        return run

    def _get_or_create_reconcile_run(
        self,
        *,
        session: Session,
        sha256: str | None,
        content_uid: str | None,
        limit: int | None,
        manifest_count: int,
        parser_name: str,
        parser_adapter_version: str,
    ) -> KbParseRun:
        filters = {
            "sha256": sha256,
            "content_uid": content_uid,
            "limit": limit,
        }

        run = KbParseRun(
            run_uid=generate_run_uid(),
            parser_name=parser_name,
            parser_adapter_version=parser_adapter_version,
            parser_family="MARKITDOWN_FAMILY",
            trigger_type=TRIGGER_RECONCILE,
            filters_json=filters,
            status=RUN_STATUS_PENDING,
            dry_run=0,
            total_candidates=manifest_count,
            in_scope_candidates=manifest_count,
        )
        session.add(run)
        session.flush()
        return run

    def _ingest_report_item(
        self,
        *,
        session: Session,
        run: KbParseRun,
        item: dict[str, Any],
        parser_name: str,
        parser_adapter_version: str,
        report_path: Path,
    ) -> dict[str, int]:
        content_uid = str(item.get("content_uid", ""))
        sha256 = str(item.get("sha256", ""))
        item_status = str(item.get("status", RESULT_STATUS_SKIPPED))

        db_content = session.scalar(
            select(KbFileContent).where(KbFileContent.content_uid == content_uid)
        )
        if db_content is None:
            raise ParseRegistryError(
                ERROR_UNKNOWN_CONTENT,
                f"Content not found in DB: content_uid={content_uid}",
            )

        parsed_dir = item.get("parsed_dir")
        if parsed_dir:
            manifest_path = Path(parsed_dir) / "parse_manifest.json"
        else:
            manifest_path = build_parsed_artifact_paths(
                build_parsed_content_dir(self.config.storage.parsed_root, sha256)
            )["parse_manifest"]

        manifest = _load_manifest(manifest_path)
        return self._persist_content_result(
            session=session,
            run=run,
            content_uid=content_uid,
            sha256=sha256,
            item_status=item_status,
            item=item,
            manifest=manifest,
            manifest_path=manifest_path,
            parser_name=parser_name,
            parser_adapter_version=parser_adapter_version,
            report_path=report_path,
        )

    def _ingest_manifest_path(
        self,
        *,
        session: Session,
        run: KbParseRun,
        manifest_path: Path,
        parser_name: str,
        parser_adapter_version: str,
    ) -> dict[str, int] | None:
        manifest = _load_manifest(manifest_path)
        if manifest is None:
            raise ParseRegistryError(
                ERROR_INVALID_MANIFEST,
                f"Invalid manifest: {manifest_path}",
            )

        content_uid = str(manifest.get("content_uid", ""))
        sha256 = str(manifest.get("sha256", ""))
        if not content_uid or not sha256:
            return None

        db_content = session.scalar(
            select(KbFileContent).where(KbFileContent.content_uid == content_uid)
        )
        if db_content is None:
            logger.warning("Orphan manifest without DB content: %s", manifest_path)
            return None

        status = str(manifest.get("status", RESULT_STATUS_SUCCESS))
        return self._persist_content_result(
            session=session,
            run=run,
            content_uid=content_uid,
            sha256=sha256,
            item_status=status,
            item={
                "route_type": manifest.get("route_type"),
                "decision": "ROUTE",
                "source_vault_path": manifest.get("source_vault_path"),
                "parsed_dir": manifest_path.parent.as_posix(),
            },
            manifest=manifest,
            manifest_path=manifest_path,
            parser_name=parser_name,
            parser_adapter_version=parser_adapter_version,
            report_path=None,
        )

    def _persist_content_result(
        self,
        *,
        session: Session,
        run: KbParseRun,
        content_uid: str,
        sha256: str,
        item_status: str,
        item: dict[str, Any],
        manifest: dict[str, Any] | None,
        manifest_path: Path,
        parser_name: str,
        parser_adapter_version: str,
        report_path: Path | None,
    ) -> dict[str, int]:
        if manifest:
            status = str(manifest.get("status", item_status))
            text_path = manifest.get("parsed_text_path")
            metadata_path = manifest.get("parsed_metadata_path")
            manifest_file_path = manifest_path.as_posix()
            output_hash = manifest.get("output_hash")
            output_size_bytes = manifest.get("output_size_bytes")
            source_vault_path = manifest.get("source_vault_path") or item.get("source_vault_path")
            route_type = manifest.get("route_type") or item.get("route_type")
            error_payload = manifest.get("error") or {}
            error_code = error_payload.get("code") if isinstance(error_payload, dict) else None
            error_message = error_payload.get("message") if isinstance(error_payload, dict) else None
            parsed_dir = item.get("parsed_dir") or manifest_path.parent.as_posix()
        else:
            status = item_status
            text_path = None
            metadata_path = None
            manifest_file_path = None
            output_hash = None
            output_size_bytes = None
            source_vault_path = item.get("source_vault_path")
            route_type = item.get("route_type")
            error_code = None
            error_message = None
            parsed_dir = item.get("parsed_dir")

            if status not in (RESULT_STATUS_SKIPPED,):
                status = RESULT_STATUS_FAILED
                error_code = ERROR_MISSING_MANIFEST
                error_message = f"Manifest missing at {manifest_path.as_posix()}"

        result_metadata: dict[str, Any] = {}
        if manifest and text_path:
            text_file = Path(str(text_path))
            if text_file.is_file() and output_hash:
                actual_hash = compute_sha256(text_file)
                if actual_hash != output_hash:
                    result_metadata["HASH_MISMATCH"] = {
                        "expected": output_hash,
                        "actual": actual_hash,
                    }

        parse_result = self.record_parse_result(
            session=session,
            run_uid=run.run_uid,
            content_uid=content_uid,
            sha256=sha256,
            status=status,
            parser_name=parser_name,
            parser_adapter_version=parser_adapter_version,
            route_type=str(route_type) if route_type else None,
            decision=str(item.get("decision")) if item.get("decision") else None,
            source_vault_path=str(source_vault_path) if source_vault_path else None,
            parsed_dir=str(parsed_dir) if parsed_dir else None,
            manifest_path=manifest_file_path,
            metadata_path=str(metadata_path) if metadata_path else None,
            text_path=str(text_path) if text_path else None,
            output_hash=str(output_hash) if output_hash else None,
            output_size_bytes=int(output_size_bytes) if output_size_bytes is not None else None,
            error_code=str(error_code) if error_code else None,
            error_message=str(error_message) if error_message else None,
            metadata=result_metadata or None,
        )

        artifact_count = 0
        if status == RESULT_STATUS_SKIPPED and manifest is None:
            self._update_parse_status(session=session, content_uid=content_uid, status=status)
            return {"artifacts": artifact_count}

        if manifest_file_path and manifest_path.is_file():
            self.record_parsed_artifact(
                session=session,
                run_uid=run.run_uid,
                content_uid=content_uid,
                sha256=sha256,
                artifact_type=ARTIFACT_TYPE_PARSE_MANIFEST,
                artifact_path=manifest_file_path,
                parser_name=parser_name,
                parser_adapter_version=parser_adapter_version,
            )
            artifact_count += 1

        if status in (RESULT_STATUS_SUCCESS, RESULT_STATUS_EMPTY):
            if text_path:
                self.record_parsed_artifact(
                    session=session,
                    run_uid=run.run_uid,
                    content_uid=content_uid,
                    sha256=sha256,
                    artifact_type=ARTIFACT_TYPE_PARSED_TEXT,
                    artifact_path=str(text_path),
                    parser_name=parser_name,
                    parser_adapter_version=parser_adapter_version,
                )
                artifact_count += 1
            if metadata_path:
                self.record_parsed_artifact(
                    session=session,
                    run_uid=run.run_uid,
                    content_uid=content_uid,
                    sha256=sha256,
                    artifact_type=ARTIFACT_TYPE_PARSED_METADATA,
                    artifact_path=str(metadata_path),
                    parser_name=parser_name,
                    parser_adapter_version=parser_adapter_version,
                )
                artifact_count += 1

        self._update_parse_status(session=session, content_uid=content_uid, status=status)
        if status in (RESULT_STATUS_SUCCESS, RESULT_STATUS_EMPTY):
            self._upsert_document(
                session=session,
                parse_result=parse_result,
                status=status,
                parser_name=parser_name,
                parser_adapter_version=parser_adapter_version,
            )

        return {"artifacts": artifact_count}

    def _update_parse_status(
        self,
        *,
        session: Session,
        content_uid: str,
        status: str,
    ) -> None:
        if status == RESULT_STATUS_SKIPPED:
            return

        parse_status: str | None
        if status == RESULT_STATUS_SUCCESS:
            parse_status = PARSE_STATUS_PARSED
        elif status == RESULT_STATUS_EMPTY:
            parse_status = PARSE_STATUS_PARSED_EMPTY
        elif status == RESULT_STATUS_FAILED:
            parse_status = PARSE_STATUS_PARSE_FAILED
        else:
            return

        content = session.scalar(
            select(KbFileContent).where(KbFileContent.content_uid == content_uid)
        )
        if content is None:
            return
        content.parse_status = parse_status
        session.add(content)

    def _upsert_document(
        self,
        *,
        session: Session,
        parse_result: KbParseResult,
        status: str,
        parser_name: str,
        parser_adapter_version: str,
    ) -> KbDocument:
        document_uid = parse_result.content_uid
        parse_status = (
            DOCUMENT_PARSE_STATUS_PARSED
            if status == RESULT_STATUS_SUCCESS
            else DOCUMENT_PARSE_STATUS_PARSED_EMPTY
        )

        existing = session.scalar(
            select(KbDocument).where(
                KbDocument.content_uid == parse_result.content_uid,
                KbDocument.parser_profile == PARSER_PROFILE_MARKITDOWN,
                KbDocument.pipeline_version == self.config.pipeline_version,
            )
        )

        text_length = (
            int(parse_result.output_size_bytes)
            if parse_result.output_size_bytes is not None
            else None
        )

        if existing is None:
            document = KbDocument(
                document_uid=document_uid,
                content_uid=parse_result.content_uid,
                source_sha256=parse_result.sha256,
                parser_name=parser_name,
                parser_version=parser_adapter_version,
                parser_profile=PARSER_PROFILE_MARKITDOWN,
                pipeline_version=self.config.pipeline_version,
                markdown_path=parse_result.text_path,
                json_path=parse_result.metadata_path,
                manifest_path=parse_result.manifest_path,
                output_dir=parse_result.parsed_dir,
                text_length=text_length,
                parse_status=parse_status,
            )
        else:
            document = existing
            document.document_uid = document_uid
            document.source_sha256 = parse_result.sha256
            document.parser_name = parser_name
            document.parser_version = parser_adapter_version
            document.markdown_path = parse_result.text_path
            document.json_path = parse_result.metadata_path
            document.manifest_path = parse_result.manifest_path
            document.output_dir = parse_result.parsed_dir
            document.text_length = text_length
            document.parse_status = parse_status

        session.add(document)
        session.flush()
        return document

    def _discover_manifests(
        self,
        *,
        target_sha: str | None,
        limit: int | None,
    ) -> list[Path]:
        parsed_root = self.config.storage.parsed_root
        if target_sha:
            manifest = build_parsed_artifact_paths(
                build_parsed_content_dir(parsed_root, target_sha)
            )["parse_manifest"]
            return [manifest] if manifest.is_file() else []

        manifests: list[Path] = []
        by_hash = parsed_root / "by_hash"
        if not by_hash.is_dir():
            return manifests

        for manifest_path in sorted(by_hash.glob("*/*/*/parse_manifest.json")):
            manifests.append(manifest_path)
            if limit is not None and len(manifests) >= limit:
                break
        return manifests

    def _build_register_preview(
        self,
        *,
        report_path: Path,
        report: dict[str, Any],
        parser_name: str,
        parser_adapter_version: str,
        items: list[Any],
    ) -> dict[str, Any]:
        would_register: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            content_uid = str(item.get("content_uid", ""))
            sha256 = str(item.get("sha256", ""))
            status = str(item.get("status", RESULT_STATUS_SKIPPED))
            parsed_dir = item.get("parsed_dir")
            manifest_exists = False
            if parsed_dir:
                manifest_exists = (Path(parsed_dir) / "parse_manifest.json").is_file()
            elif sha256:
                manifest_path = build_parsed_artifact_paths(
                    build_parsed_content_dir(self.config.storage.parsed_root, sha256)
                )["parse_manifest"]
                manifest_exists = manifest_path.is_file()

            artifact_types: list[str] = []
            if status == RESULT_STATUS_SKIPPED and not manifest_exists:
                artifact_types = []
            elif status in (RESULT_STATUS_SUCCESS, RESULT_STATUS_EMPTY) and manifest_exists:
                artifact_types = [
                    ARTIFACT_TYPE_PARSE_MANIFEST,
                    ARTIFACT_TYPE_PARSED_TEXT,
                    ARTIFACT_TYPE_PARSED_METADATA,
                ]
            elif manifest_exists:
                artifact_types = [ARTIFACT_TYPE_PARSE_MANIFEST]

            would_register.append(
                {
                    "content_uid": content_uid,
                    "sha256": sha256,
                    "status": status,
                    "artifact_types": artifact_types,
                }
            )

        return {
            "parser_name": parser_name,
            "parser_adapter_version": parser_adapter_version,
            "source_report_path": report_path.as_posix(),
            "would_register": would_register,
            "would_index_parse_report": True,
        }

    def _write_registry_report(self, payload: dict[str, Any]) -> Path:
        reports_root = self.config.storage.reports_root
        reports_root.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        report_path = reports_root / f"registry_report_{timestamp}.json"
        report_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return report_path
