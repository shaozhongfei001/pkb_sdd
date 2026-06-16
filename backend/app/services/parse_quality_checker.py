from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import AppConfig, ensure_readonly
from app.core.database import create_db_engine, create_session_factory
from app.core.parsed_paths import build_parsed_artifact_paths, build_parsed_content_dir
from app.core.vault_paths import build_vault_artifact_paths
from app.models.file import KbFileContent
from app.models.parse_registry import KbParseResult, KbParsedArtifact
from app.models.vault import KbRawVaultObject

logger = logging.getLogger(__name__)

REPORT_TYPE = "parse_quality_report"
SCHEMA_VERSION = "1.0"
MODE_CHECK = "check"

ALLOWED_PARSER_NAMES = frozenset({"markitdown", "mineru"})
ALLOWED_RESULT_STATUSES = frozenset({"SUCCESS", "EMPTY", "SKIPPED", "FAILED"})
STALE_PATH_MARKERS = ("/tmp/", "/var/tmp/", "/private/tmp/")

ISSUE_CODES: tuple[str, ...] = (
    "MISSING_RAW_VAULT_OBJECT",
    "STALE_RAW_VAULT_PATH",
    "MISSING_PARSED_DIR",
    "MISSING_PARSED_TEXT",
    "MISSING_PARSED_METADATA",
    "MISSING_PARSE_MANIFEST",
    "INVALID_PARSE_MANIFEST_JSON",
    "MANIFEST_REQUIRED_FIELD_MISSING",
    "MANIFEST_SHA256_MISMATCH",
    "MANIFEST_CONTENT_UID_MISMATCH",
    "MANIFEST_PARSER_NAME_INVALID",
    "MANIFEST_ADAPTER_VERSION_MISSING",
    "REGISTRY_ARTIFACT_PATH_MISSING",
    "REGISTRY_STATUS_FILE_MISMATCH",
    "REGISTRY_MISSING_MANIFEST_RESULT",
    "REGISTRY_FAILED_RESULT",
    "REGISTRY_EMPTY_RESULT",
    "REGISTRY_SKIPPED_RESULT",
)

SEVERITY_CRITICAL = "CRITICAL"
SEVERITY_ERROR = "ERROR"
SEVERITY_WARNING = "WARNING"
SEVERITY_INFO = "INFO"

ERROR_MISSING_MANIFEST = "MISSING_MANIFEST"

COMMON_MANIFEST_REQUIRED_FIELDS = (
    "content_uid",
    "sha256",
    "parser_name",
    "parser_adapter_version",
    "status",
    "generated_at",
)
MINERU_MANIFEST_REQUIRED_FIELDS = ("parser_profile",)
SUCCESS_MANIFEST_ARTIFACT_FIELDS = ("parsed_text_path", "parsed_metadata_path")

RECOMMENDATION_BY_CODE: dict[str, str] = {
    "MISSING_RAW_VAULT_OBJECT": (
        "Re-run copy-to-vault for missing raw vault object after manual review."
    ),
    "STALE_RAW_VAULT_PATH": (
        "Review stale /tmp vault path and rebuild vault object if needed."
    ),
    "MISSING_PARSED_DIR": (
        "Re-run parser only after raw vault sample is restored."
    ),
    "MISSING_PARSED_TEXT": (
        "Re-run parser only after raw vault sample is restored."
    ),
    "MISSING_PARSED_METADATA": (
        "Re-run parser only after raw vault sample is restored."
    ),
    "MISSING_PARSE_MANIFEST": (
        "Re-run parser or reconcile-parsed-artifacts after manual review."
    ),
    "INVALID_PARSE_MANIFEST_JSON": (
        "Inspect parse_manifest.json manually; re-run parser if repair is approved."
    ),
    "MANIFEST_REQUIRED_FIELD_MISSING": (
        "Inspect parse_manifest.json against the 005/007 contract."
    ),
    "MANIFEST_SHA256_MISMATCH": (
        "Verify content identity and re-parse only after manual approval."
    ),
    "MANIFEST_CONTENT_UID_MISMATCH": (
        "Verify content identity and re-parse only after manual approval."
    ),
    "MANIFEST_PARSER_NAME_INVALID": (
        "Review parser routing and registry records for this content."
    ),
    "MANIFEST_ADAPTER_VERSION_MISSING": (
        "Inspect parse_manifest.json for missing parser_adapter_version."
    ),
    "REGISTRY_ARTIFACT_PATH_MISSING": (
        "Reconcile registry artifact paths or re-run parser after manual review."
    ),
    "REGISTRY_STATUS_FILE_MISMATCH": (
        "Registry SUCCESS contradicts filesystem; review before re-parsing."
    ),
    "REGISTRY_MISSING_MANIFEST_RESULT": (
        "Review registry result with missing manifest before re-parsing."
    ),
    "REGISTRY_FAILED_RESULT": (
        "Review failed parse result; re-run parser only after root cause is fixed."
    ),
    "REGISTRY_EMPTY_RESULT": (
        "Review empty parse result to confirm source content is expected to be empty."
    ),
    "REGISTRY_SKIPPED_RESULT": (
        "Skipped parse result recorded for review; no automatic action required."
    ),
}


@dataclass
class ParseQualityCandidate:
    content_uid: str
    sha256: str
    parser_name: str
    parser_adapter_version: str
    result_status: str
    route_type: str | None
    run_uid: str
    result_uid: str
    parsed_dir: str | None
    manifest_path: str | None
    source_vault_path: str | None
    error_code: str | None


@dataclass
class ParseQualityIssue:
    issue_code: str
    severity: str
    content_uid: str | None
    sha256: str | None
    parser_name: str | None
    parser_adapter_version: str | None
    artifact_type: str | None
    path: str | None
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "issue_code": self.issue_code,
            "severity": self.severity,
            "content_uid": self.content_uid,
            "sha256": self.sha256,
            "parser_name": self.parser_name,
            "parser_adapter_version": self.parser_adapter_version,
            "artifact_type": self.artifact_type,
            "path": self.path,
            "message": self.message,
            "evidence": self.evidence,
        }


@dataclass
class ParseQualityReport:
    scope: dict[str, Any]
    summary: dict[str, int]
    issue_counts: dict[str, int]
    by_parser: dict[str, int]
    by_status: dict[str, int]
    by_route_type: dict[str, int]
    by_severity: dict[str, int]
    issues: list[ParseQualityIssue]
    recommendations: list[str]
    generated_at: str
    report_path: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_type": REPORT_TYPE,
            "schema_version": SCHEMA_VERSION,
            "generated_at": self.generated_at,
            "mode": MODE_CHECK,
            "scope": self.scope,
            "summary": self.summary,
            "issue_counts": self.issue_counts,
            "by_parser": self.by_parser,
            "by_status": self.by_status,
            "by_route_type": self.by_route_type,
            "by_severity": self.by_severity,
            "issues": [issue.to_dict() for issue in self.issues],
            "recommendations": self.recommendations,
        }


def _utc_iso() -> str:
    return datetime.now(UTC).replace(tzinfo=UTC).isoformat().replace("+00:00", "Z")


def _report_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _empty_issue_counts() -> dict[str, int]:
    return {code: 0 for code in ISSUE_CODES}


def _is_stale_path(path_value: str | None) -> bool:
    if not path_value:
        return False
    normalized = path_value.replace("\\", "/")
    return any(marker in normalized for marker in STALE_PATH_MARKERS)


def _increment(bucket: dict[str, int], key: str | None) -> None:
    label = key if key else "(null)"
    bucket[label] = bucket.get(label, 0) + 1


class ParseQualityCheckerService:
    def __init__(
        self,
        config: AppConfig,
        session_factory: sessionmaker[Session] | None = None,
    ) -> None:
        ensure_readonly(config)
        self.config = config
        if session_factory is None:
            engine = create_db_engine(config)
            self.session_factory = create_session_factory(engine)
        else:
            self.session_factory = session_factory

    def check(
        self,
        *,
        sha256: str | None = None,
        content_uid: str | None = None,
        parser_name: str | None = None,
        status: str | None = None,
        limit: int | None = None,
        output: Path | None = None,
    ) -> ParseQualityReport:
        if parser_name is not None and parser_name not in ALLOWED_PARSER_NAMES:
            raise ValueError(
                f"parser_name must be one of {sorted(ALLOWED_PARSER_NAMES)}: {parser_name!r}"
            )
        if status is not None and status not in ALLOWED_RESULT_STATUSES:
            raise ValueError(
                f"status must be one of {sorted(ALLOWED_RESULT_STATUSES)}: {status!r}"
            )
        if limit is not None and limit < 1:
            raise ValueError("--limit must be >= 1")

        scope = {
            "sha256": sha256,
            "content_uid": content_uid,
            "parser_name": parser_name,
            "status": status,
            "limit": limit,
        }
        generated_at = _utc_iso()

        with self.session_factory() as session:
            candidates = self._load_candidates(
                session=session,
                sha256=sha256,
                content_uid=content_uid,
                parser_name=parser_name,
                status=status,
                limit=limit,
            )
            issues: list[ParseQualityIssue] = []
            checked_raw_vault: set[str] = set()
            checked_artifact_ids: set[int] = set()

            for candidate in candidates:
                vault_object = session.scalar(
                    select(KbRawVaultObject).where(KbRawVaultObject.sha256 == candidate.sha256)
                )
                if vault_object is not None:
                    checked_raw_vault.add(vault_object.sha256)
                    issues.extend(self._check_raw_vault(vault_object))

                issues.extend(self._check_stale_source_path(candidate))

                parsed_dir = self._resolve_parsed_dir(candidate)
                artifact_paths = build_parsed_artifact_paths(parsed_dir)
                issues.extend(self._check_parsed_files(candidate, parsed_dir, artifact_paths))

                manifest_path = self._resolve_manifest_path(candidate, artifact_paths)
                manifest, manifest_issues = self._load_and_validate_manifest(
                    session=session,
                    candidate=candidate,
                    manifest_path=manifest_path,
                )
                issues.extend(manifest_issues)

                if manifest is not None:
                    route_type = candidate.route_type or manifest.get("route_type")
                    if route_type is None and isinstance(manifest.get("route_type"), str):
                        route_type = manifest["route_type"]
                    candidate.route_type = str(route_type) if route_type else None
                    issues.extend(
                        self._check_stale_manifest_source_path(candidate, manifest)
                    )

                issues.extend(
                    self._check_registry_status_files(
                        candidate=candidate,
                        parsed_dir=parsed_dir,
                        artifact_paths=artifact_paths,
                    )
                )
                issues.extend(self._check_registry_status_aggregation(candidate))

                registry_artifacts = session.scalars(
                    select(KbParsedArtifact).where(
                        KbParsedArtifact.run_uid == candidate.run_uid,
                        KbParsedArtifact.content_uid == candidate.content_uid,
                    )
                ).all()
                for registry_artifact in registry_artifacts:
                    checked_artifact_ids.add(registry_artifact.id)
                    issues.extend(self._check_registry_artifact(registry_artifact))

        issue_counts = _empty_issue_counts()
        by_parser: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_route_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        severity_summary = {
            SEVERITY_CRITICAL: 0,
            SEVERITY_ERROR: 0,
            SEVERITY_WARNING: 0,
            SEVERITY_INFO: 0,
        }

        candidate_by_uid = {candidate.content_uid: candidate for candidate in candidates}

        for issue in issues:
            issue_counts[issue.issue_code] = issue_counts.get(issue.issue_code, 0) + 1
            _increment(by_parser, issue.parser_name)
            candidate = (
                candidate_by_uid.get(issue.content_uid)
                if issue.content_uid is not None
                else None
            )
            if candidate is not None:
                _increment(by_status, candidate.result_status)
                _increment(by_route_type, candidate.route_type)
            _increment(by_severity, issue.severity)
            if issue.severity in severity_summary:
                severity_summary[issue.severity] += 1

        unique_content_uids = {candidate.content_uid for candidate in candidates}
        summary = {
            "checked_content_count": len(unique_content_uids),
            "checked_raw_vault_count": len(checked_raw_vault),
            "checked_parse_result_count": len(candidates),
            "checked_artifact_count": len(checked_artifact_ids),
            "issue_count": len(issues),
            "critical_count": severity_summary[SEVERITY_CRITICAL],
            "error_count": severity_summary[SEVERITY_ERROR],
            "warning_count": severity_summary[SEVERITY_WARNING],
            "info_count": severity_summary[SEVERITY_INFO],
        }

        recommendations = self._build_recommendations(issues)
        report = ParseQualityReport(
            scope=scope,
            summary=summary,
            issue_counts=issue_counts,
            by_parser=by_parser,
            by_status=by_status,
            by_route_type=by_route_type,
            by_severity=by_severity,
            issues=issues,
            recommendations=recommendations,
            generated_at=generated_at,
        )
        report.report_path = self._write_report(report, output)
        return report

    def _load_candidates(
        self,
        *,
        session: Session,
        sha256: str | None,
        content_uid: str | None,
        parser_name: str | None,
        status: str | None,
        limit: int | None,
    ) -> list[ParseQualityCandidate]:
        query = select(KbParseResult).order_by(KbParseResult.id.desc())
        if sha256:
            query = query.where(KbParseResult.sha256 == sha256)
        if content_uid:
            query = query.where(KbParseResult.content_uid == content_uid)
        if parser_name:
            query = query.where(KbParseResult.parser_name == parser_name)
        if status:
            query = query.where(KbParseResult.status == status)
        if limit is not None:
            query = query.limit(limit)
        results = session.scalars(query).all()
        return [
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
            for result in results
        ]

    def _resolve_parsed_dir(self, candidate: ParseQualityCandidate) -> Path:
        if candidate.parsed_dir:
            return Path(candidate.parsed_dir)
        return build_parsed_content_dir(self.config.storage.parsed_root, candidate.sha256)

    def _resolve_manifest_path(
        self,
        candidate: ParseQualityCandidate,
        artifact_paths: dict[str, Path],
    ) -> Path:
        if candidate.manifest_path:
            return Path(candidate.manifest_path)
        return artifact_paths["parse_manifest"]

    def _check_raw_vault(self, vault_object: KbRawVaultObject) -> list[ParseQualityIssue]:
        issues: list[ParseQualityIssue] = []
        vault_dir = Path(vault_object.vault_path)
        original_bin = build_vault_artifact_paths(vault_dir)["original_bin"]

        if _is_stale_path(vault_object.vault_path):
            issues.append(
                ParseQualityIssue(
                    issue_code="STALE_RAW_VAULT_PATH",
                    severity=SEVERITY_WARNING,
                    content_uid=vault_object.content_uid,
                    sha256=vault_object.sha256,
                    parser_name=None,
                    parser_adapter_version=None,
                    artifact_type="RAW_VAULT",
                    path=vault_object.vault_path,
                    message="Raw vault path points to a suspicious temporary location",
                    evidence={"vault_path": vault_object.vault_path},
                )
            )

        if not original_bin.is_file():
            issues.append(
                ParseQualityIssue(
                    issue_code="MISSING_RAW_VAULT_OBJECT",
                    severity=SEVERITY_ERROR,
                    content_uid=vault_object.content_uid,
                    sha256=vault_object.sha256,
                    parser_name=None,
                    parser_adapter_version=None,
                    artifact_type="RAW_VAULT",
                    path=original_bin.as_posix(),
                    message="raw_vault original.bin is missing",
                    evidence={
                        "vault_path": vault_object.vault_path,
                        "original_bin": original_bin.as_posix(),
                    },
                )
            )
        return issues

    def _check_stale_source_path(
        self,
        candidate: ParseQualityCandidate,
    ) -> list[ParseQualityIssue]:
        if not _is_stale_path(candidate.source_vault_path):
            return []
        return [
            ParseQualityIssue(
                issue_code="STALE_RAW_VAULT_PATH",
                severity=SEVERITY_WARNING,
                content_uid=candidate.content_uid,
                sha256=candidate.sha256,
                parser_name=candidate.parser_name,
                parser_adapter_version=candidate.parser_adapter_version,
                artifact_type="RAW_VAULT",
                path=candidate.source_vault_path,
                message="Registry source_vault_path points to a suspicious temporary location",
                evidence={"source_vault_path": candidate.source_vault_path},
            )
        ]

    def _check_stale_manifest_source_path(
        self,
        candidate: ParseQualityCandidate,
        manifest: dict[str, Any],
    ) -> list[ParseQualityIssue]:
        source_vault_path = manifest.get("source_vault_path")
        if not isinstance(source_vault_path, str) or not _is_stale_path(source_vault_path):
            return []
        if candidate.source_vault_path == source_vault_path:
            return []
        return [
            ParseQualityIssue(
                issue_code="STALE_RAW_VAULT_PATH",
                severity=SEVERITY_WARNING,
                content_uid=candidate.content_uid,
                sha256=candidate.sha256,
                parser_name=candidate.parser_name,
                parser_adapter_version=candidate.parser_adapter_version,
                artifact_type="RAW_VAULT",
                path=source_vault_path,
                message="Manifest source_vault_path points to a suspicious temporary location",
                evidence={"source_vault_path": source_vault_path},
            )
        ]

    def _check_parsed_files(
        self,
        candidate: ParseQualityCandidate,
        parsed_dir: Path,
        artifact_paths: dict[str, Path],
    ) -> list[ParseQualityIssue]:
        issues: list[ParseQualityIssue] = []
        base_kwargs = {
            "content_uid": candidate.content_uid,
            "sha256": candidate.sha256,
            "parser_name": candidate.parser_name,
            "parser_adapter_version": candidate.parser_adapter_version,
        }

        if not parsed_dir.is_dir():
            issues.append(
                ParseQualityIssue(
                    issue_code="MISSING_PARSED_DIR",
                    severity=SEVERITY_ERROR,
                    artifact_type="PARSED_DIR",
                    path=parsed_dir.as_posix(),
                    message="Expected parsed directory is missing",
                    evidence={"parsed_dir": parsed_dir.as_posix()},
                    **base_kwargs,
                )
            )
            return issues

        for code, key, artifact_type in (
            ("MISSING_PARSED_TEXT", "parsed_text", "PARSED_TEXT"),
            ("MISSING_PARSED_METADATA", "parsed_metadata", "PARSED_METADATA"),
            ("MISSING_PARSE_MANIFEST", "parse_manifest", "PARSE_MANIFEST"),
        ):
            file_path = artifact_paths[key]
            if not file_path.is_file():
                issues.append(
                    ParseQualityIssue(
                        issue_code=code,
                        severity=SEVERITY_ERROR,
                        artifact_type=artifact_type,
                        path=file_path.as_posix(),
                        message=f"Required parsed artifact is missing: {file_path.name}",
                        evidence={"parsed_dir": parsed_dir.as_posix()},
                        **base_kwargs,
                    )
                )
        return issues

    def _load_and_validate_manifest(
        self,
        *,
        session: Session,
        candidate: ParseQualityCandidate,
        manifest_path: Path,
    ) -> tuple[dict[str, Any] | None, list[ParseQualityIssue]]:
        issues: list[ParseQualityIssue] = []
        base_kwargs = {
            "content_uid": candidate.content_uid,
            "sha256": candidate.sha256,
            "parser_name": candidate.parser_name,
            "parser_adapter_version": candidate.parser_adapter_version,
            "artifact_type": "PARSE_MANIFEST",
            "path": manifest_path.as_posix(),
        }

        if not manifest_path.is_file():
            return None, issues

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            issues.append(
                ParseQualityIssue(
                    issue_code="INVALID_PARSE_MANIFEST_JSON",
                    severity=SEVERITY_ERROR,
                    message=f"parse_manifest.json is not valid JSON: {exc}",
                    evidence={"manifest_path": manifest_path.as_posix()},
                    **base_kwargs,
                )
            )
            return None, issues

        if not isinstance(manifest, dict):
            issues.append(
                ParseQualityIssue(
                    issue_code="INVALID_PARSE_MANIFEST_JSON",
                    severity=SEVERITY_ERROR,
                    message="parse_manifest.json root must be a JSON object",
                    evidence={"manifest_path": manifest_path.as_posix()},
                    **base_kwargs,
                )
            )
            return None, issues

        required_fields = list(COMMON_MANIFEST_REQUIRED_FIELDS)
        if manifest.get("parser_name") == "mineru":
            required_fields.extend(MINERU_MANIFEST_REQUIRED_FIELDS)
        if manifest.get("status") == "SUCCESS":
            required_fields.extend(SUCCESS_MANIFEST_ARTIFACT_FIELDS)

        missing_fields = [
            field_name
            for field_name in required_fields
            if field_name not in manifest or manifest.get(field_name) in (None, "")
        ]
        if missing_fields:
            issues.append(
                ParseQualityIssue(
                    issue_code="MANIFEST_REQUIRED_FIELD_MISSING",
                    severity=SEVERITY_ERROR,
                    message=f"Manifest missing required fields: {', '.join(missing_fields)}",
                    evidence={"missing_fields": missing_fields},
                    **base_kwargs,
                )
            )

        manifest_sha256 = manifest.get("sha256")
        if isinstance(manifest_sha256, str) and manifest_sha256 != candidate.sha256:
            issues.append(
                ParseQualityIssue(
                    issue_code="MANIFEST_SHA256_MISMATCH",
                    severity=SEVERITY_CRITICAL,
                    message="Manifest sha256 does not match registry/content sha256",
                    evidence={
                        "manifest_sha256": manifest_sha256,
                        "expected_sha256": candidate.sha256,
                    },
                    **base_kwargs,
                )
            )

        manifest_content_uid = manifest.get("content_uid")
        if (
            isinstance(manifest_content_uid, str)
            and manifest_content_uid != candidate.content_uid
        ):
            issues.append(
                ParseQualityIssue(
                    issue_code="MANIFEST_CONTENT_UID_MISMATCH",
                    severity=SEVERITY_CRITICAL,
                    message="Manifest content_uid does not match registry content_uid",
                    evidence={
                        "manifest_content_uid": manifest_content_uid,
                        "expected_content_uid": candidate.content_uid,
                    },
                    **base_kwargs,
                )
            )

        manifest_parser_name = manifest.get("parser_name")
        if manifest_parser_name is not None and manifest_parser_name not in ALLOWED_PARSER_NAMES:
            issues.append(
                ParseQualityIssue(
                    issue_code="MANIFEST_PARSER_NAME_INVALID",
                    severity=SEVERITY_ERROR,
                    message=f"Manifest parser_name is not allowed: {manifest_parser_name!r}",
                    evidence={"parser_name": manifest_parser_name},
                    **base_kwargs,
                )
            )
        elif (
            isinstance(manifest_parser_name, str)
            and manifest_parser_name != candidate.parser_name
        ):
            issues.append(
                ParseQualityIssue(
                    issue_code="MANIFEST_PARSER_NAME_INVALID",
                    severity=SEVERITY_ERROR,
                    message="Manifest parser_name does not match registry parser_name",
                    evidence={
                        "manifest_parser_name": manifest_parser_name,
                        "registry_parser_name": candidate.parser_name,
                    },
                    **base_kwargs,
                )
            )

        if not manifest.get("parser_adapter_version"):
            issues.append(
                ParseQualityIssue(
                    issue_code="MANIFEST_ADAPTER_VERSION_MISSING",
                    severity=SEVERITY_ERROR,
                    message="Manifest parser_adapter_version is missing",
                    evidence={},
                    **base_kwargs,
                )
            )

        db_content = session.scalar(
            select(KbFileContent).where(KbFileContent.sha256 == candidate.sha256)
        )
        if db_content is not None and isinstance(manifest_sha256, str):
            if manifest_sha256 != db_content.sha256:
                if not any(
                    issue.issue_code == "MANIFEST_SHA256_MISMATCH" for issue in issues
                ):
                    issues.append(
                        ParseQualityIssue(
                            issue_code="MANIFEST_SHA256_MISMATCH",
                            severity=SEVERITY_CRITICAL,
                            message="Manifest sha256 does not match kb_file_content.sha256",
                            evidence={
                                "manifest_sha256": manifest_sha256,
                                "db_sha256": db_content.sha256,
                            },
                            **base_kwargs,
                        )
                    )

        if candidate.route_type is None:
            route_type = manifest.get("route_type")
            if isinstance(route_type, str):
                candidate.route_type = route_type

        return manifest, issues

    def _check_registry_status_files(
        self,
        *,
        candidate: ParseQualityCandidate,
        parsed_dir: Path,
        artifact_paths: dict[str, Path],
    ) -> list[ParseQualityIssue]:
        if candidate.result_status != "SUCCESS":
            return []
        missing_paths = [
            artifact_paths[key].as_posix()
            for key in ("parsed_text", "parsed_metadata", "parse_manifest")
            if not artifact_paths[key].is_file()
        ]
        if not missing_paths and parsed_dir.is_dir():
            return []
        return [
            ParseQualityIssue(
                issue_code="REGISTRY_STATUS_FILE_MISMATCH",
                severity=SEVERITY_CRITICAL,
                content_uid=candidate.content_uid,
                sha256=candidate.sha256,
                parser_name=candidate.parser_name,
                parser_adapter_version=candidate.parser_adapter_version,
                artifact_type=None,
                path=parsed_dir.as_posix(),
                message="Registry status is SUCCESS but required parsed artifacts are missing",
                evidence={
                    "result_status": candidate.result_status,
                    "missing_paths": missing_paths,
                },
            )
        ]

    def _check_registry_status_aggregation(
        self,
        candidate: ParseQualityCandidate,
    ) -> list[ParseQualityIssue]:
        if candidate.error_code == ERROR_MISSING_MANIFEST:
            return [
                ParseQualityIssue(
                    issue_code="REGISTRY_MISSING_MANIFEST_RESULT",
                    severity=SEVERITY_WARNING,
                    content_uid=candidate.content_uid,
                    sha256=candidate.sha256,
                    parser_name=candidate.parser_name,
                    parser_adapter_version=candidate.parser_adapter_version,
                    artifact_type="PARSE_MANIFEST",
                    path=candidate.manifest_path,
                    message="Registry result indicates missing manifest",
                    evidence={"error_code": candidate.error_code},
                )
            ]
        if candidate.result_status == "FAILED":
            return [
                ParseQualityIssue(
                    issue_code="REGISTRY_FAILED_RESULT",
                    severity=SEVERITY_WARNING,
                    content_uid=candidate.content_uid,
                    sha256=candidate.sha256,
                    parser_name=candidate.parser_name,
                    parser_adapter_version=candidate.parser_adapter_version,
                    artifact_type=None,
                    path=None,
                    message="Registry parse result status is FAILED",
                    evidence={
                        "result_status": candidate.result_status,
                        "error_code": candidate.error_code,
                    },
                )
            ]
        if candidate.result_status == "EMPTY":
            return [
                ParseQualityIssue(
                    issue_code="REGISTRY_EMPTY_RESULT",
                    severity=SEVERITY_WARNING,
                    content_uid=candidate.content_uid,
                    sha256=candidate.sha256,
                    parser_name=candidate.parser_name,
                    parser_adapter_version=candidate.parser_adapter_version,
                    artifact_type=None,
                    path=None,
                    message="Registry parse result status is EMPTY",
                    evidence={"result_status": candidate.result_status},
                )
            ]
        if candidate.result_status == "SKIPPED":
            return [
                ParseQualityIssue(
                    issue_code="REGISTRY_SKIPPED_RESULT",
                    severity=SEVERITY_INFO,
                    content_uid=candidate.content_uid,
                    sha256=candidate.sha256,
                    parser_name=candidate.parser_name,
                    parser_adapter_version=candidate.parser_adapter_version,
                    artifact_type=None,
                    path=None,
                    message="Registry parse result status is SKIPPED",
                    evidence={"result_status": candidate.result_status},
                )
            ]
        return []

    def _check_registry_artifact(
        self,
        artifact: KbParsedArtifact,
    ) -> list[ParseQualityIssue]:
        artifact_path = Path(artifact.artifact_path)
        if artifact_path.is_file():
            return []
        return [
            ParseQualityIssue(
                issue_code="REGISTRY_ARTIFACT_PATH_MISSING",
                severity=SEVERITY_ERROR,
                content_uid=artifact.content_uid or None,
                sha256=artifact.sha256,
                parser_name=artifact.parser_name,
                parser_adapter_version=artifact.parser_adapter_version,
                artifact_type=artifact.artifact_type,
                path=artifact.artifact_path,
                message="Registry artifact path points to a missing file",
                evidence={
                    "artifact_uid": artifact.artifact_uid,
                    "artifact_type": artifact.artifact_type,
                },
            )
        ]

    def _build_recommendations(self, issues: list[ParseQualityIssue]) -> list[str]:
        seen: set[str] = set()
        recommendations: list[str] = []
        for issue in issues:
            recommendation = RECOMMENDATION_BY_CODE.get(issue.issue_code)
            if recommendation and recommendation not in seen:
                seen.add(recommendation)
                recommendations.append(recommendation)
        return recommendations

    def _write_report(
        self,
        report: ParseQualityReport,
        output: Path | None,
    ) -> Path:
        reports_root = self.config.storage.reports_root
        reports_root.mkdir(parents=True, exist_ok=True)
        report_path = output or (
            reports_root / f"parse_quality_report_{_report_timestamp()}.json"
        )
        try:
            report_path.write_text(
                json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            raise RuntimeError(f"Report directory not writable: {exc}") from exc
        logger.info("Wrote parse quality report: %s", report_path)
        return report_path
