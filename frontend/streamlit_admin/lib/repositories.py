from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import AppConfig
from app.models.document import KbDocument
from app.models.evidence import KbDocumentChunk, KbEvidence
from app.models.file import KbFileContent, KbFileInstance
from app.models.parse_registry import KbParseResult, KbParseRun, KbParsedArtifact
from app.models.project import KbCuratedAsset, KbProject, KbProjectDocument
from app.models.vault import KbRawVaultObject

from streamlit_admin.lib.safe_paths import read_text_under_root

REPORT_JSON_PATTERN = re.compile(r"^parse_quality_report_.*\.json$")
REPORT_SUMMARY_MD_PATTERN = re.compile(r"^parse_quality_summary_.*\.md$")
REPORT_SUMMARY_JSON_PATTERN = re.compile(r"^parse_quality_summary_.*\.json$")


@dataclass(frozen=True)
class EvidenceRow:
    evidence_uid: str
    document_uid: str
    content_uid: str
    chunk_uid: str | None
    evidence_type: str | None
    quote_text: str | None
    normalized_text: str | None
    source_location: str | None
    page_no: int | None
    heading_path: str | None
    created_at: datetime | None
    document_title: str | None
    chunk_preview: str | None


@dataclass(frozen=True)
class ProjectRow:
    project_uid: str
    project_code: str
    project_name: str
    document_count: int
    status: str


@dataclass(frozen=True)
class CuratedAssetRow:
    curated_uid: str
    project_uid: str | None
    project_code: str | None
    asset_type: str
    asset_title: str | None
    curated_path: str


@dataclass(frozen=True)
class ParseRunRow:
    run_uid: str
    parser_name: str
    parser_adapter_version: str
    parser_family: str
    status: str
    total_candidates: int
    parsed_count: int
    failed_count: int
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime | None


@dataclass(frozen=True)
class ReportFileRow:
    name: str
    path: Path
    kind: str
    mtime: float


def list_evidence(
    session: Session,
    *,
    evidence_uid: str | None = None,
    document_uid: str | None = None,
    content_uid: str | None = None,
    chunk_uid: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[EvidenceRow], int]:
    stmt = (
        select(KbEvidence, KbDocument.title, KbDocumentChunk.content)
        .outerjoin(KbDocument, KbDocument.document_uid == KbEvidence.document_uid)
        .outerjoin(KbDocumentChunk, KbDocumentChunk.chunk_uid == KbEvidence.chunk_uid)
    )
    if evidence_uid:
        stmt = stmt.where(KbEvidence.evidence_uid == evidence_uid.strip())
    if document_uid:
        stmt = stmt.where(KbEvidence.document_uid == document_uid.strip())
    if content_uid:
        stmt = stmt.where(KbEvidence.content_uid == content_uid.strip())
    if chunk_uid:
        stmt = stmt.where(KbEvidence.chunk_uid == chunk_uid.strip())

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = session.execute(count_stmt).scalar_one()

    rows = session.execute(
        stmt.order_by(KbEvidence.created_at.desc()).limit(limit).offset(offset)
    ).all()

    result = [
        EvidenceRow(
            evidence_uid=ev.evidence_uid,
            document_uid=ev.document_uid,
            content_uid=ev.content_uid,
            chunk_uid=ev.chunk_uid,
            evidence_type=ev.evidence_type,
            quote_text=ev.quote_text,
            normalized_text=ev.normalized_text,
            source_location=ev.source_location,
            page_no=ev.page_no,
            heading_path=ev.heading_path,
            created_at=ev.created_at,
            document_title=title,
            chunk_preview=(chunk_content[:200] if chunk_content else None),
        )
        for ev, title, chunk_content in rows
    ]
    return result, total


def list_projects(session: Session) -> list[ProjectRow]:
    rows = session.execute(
        select(KbProject).order_by(KbProject.project_code)
    ).scalars().all()
    return [
        ProjectRow(
            project_uid=p.project_uid,
            project_code=p.project_code,
            project_name=p.project_name,
            document_count=p.document_count,
            status=p.status,
        )
        for p in rows
    ]


def list_project_documents(
    session: Session, project_uid: str
) -> list[dict[str, str]]:
    rows = session.execute(
        select(KbProjectDocument).where(KbProjectDocument.project_uid == project_uid)
    ).scalars().all()
    return [
        {
            "document_uid": r.document_uid,
            "content_uid": r.content_uid,
            "mapping_method": r.mapping_method or "",
        }
        for r in rows
    ]


def list_curated_assets(
    session: Session, project_uid: str | None = None
) -> list[CuratedAssetRow]:
    stmt = (
        select(KbCuratedAsset, KbProject.project_code)
        .outerjoin(KbProject, KbProject.project_uid == KbCuratedAsset.project_uid)
        .order_by(KbCuratedAsset.asset_title)
    )
    if project_uid:
        stmt = stmt.where(KbCuratedAsset.project_uid == project_uid)

    rows = session.execute(stmt).all()
    return [
        CuratedAssetRow(
            curated_uid=asset.curated_uid,
            project_uid=asset.project_uid,
            project_code=code,
            asset_type=asset.asset_type,
            asset_title=asset.asset_title,
            curated_path=asset.curated_path,
        )
        for asset, code in rows
    ]


def read_curated_markdown(config: AppConfig, curated_path: str) -> str:
    return read_text_under_root(config.storage.curated_root, curated_path)


def list_parse_runs(session: Session, *, limit: int = 50) -> list[ParseRunRow]:
    rows = session.execute(
        select(KbParseRun).order_by(KbParseRun.created_at.desc()).limit(limit)
    ).scalars().all()
    return [
        ParseRunRow(
            run_uid=r.run_uid,
            parser_name=r.parser_name,
            parser_adapter_version=r.parser_adapter_version,
            parser_family=r.parser_family,
            status=r.status,
            total_candidates=r.total_candidates,
            parsed_count=r.parsed_count,
            failed_count=r.failed_count,
            started_at=r.started_at,
            finished_at=r.finished_at,
            created_at=r.created_at,
        )
        for r in rows
    ]


def get_parse_run_detail(
    session: Session, run_uid: str
) -> tuple[ParseRunRow | None, list[dict[str, Any]], list[dict[str, Any]]]:
    run = session.execute(
        select(KbParseRun).where(KbParseRun.run_uid == run_uid)
    ).scalar_one_or_none()
    if run is None:
        return None, [], []

    run_row = ParseRunRow(
        run_uid=run.run_uid,
        parser_name=run.parser_name,
        parser_adapter_version=run.parser_adapter_version,
        parser_family=run.parser_family,
        status=run.status,
        total_candidates=run.total_candidates,
        parsed_count=run.parsed_count,
        failed_count=run.failed_count,
        started_at=run.started_at,
        finished_at=run.finished_at,
        created_at=run.created_at,
    )

    results = session.execute(
        select(KbParseResult).where(KbParseResult.run_uid == run_uid)
    ).scalars().all()
    artifacts = session.execute(
        select(KbParsedArtifact).where(KbParsedArtifact.run_uid == run_uid)
    ).scalars().all()

    result_rows = [
        {
            "result_uid": r.result_uid,
            "content_uid": r.content_uid,
            "sha256": r.sha256,
            "status": r.status,
            "parser_name": r.parser_name,
            "error_code": r.error_code,
            "created_at": r.created_at,
        }
        for r in results
    ]
    artifact_rows = [
        {
            "artifact_uid": a.artifact_uid,
            "content_uid": a.content_uid,
            "artifact_type": a.artifact_type,
            "artifact_path": a.artifact_path,
            "status": a.status,
            "parser_name": a.parser_name,
        }
        for a in artifacts
    ]
    return run_row, result_rows, artifact_rows


def _classify_report_name(name: str) -> str | None:
    if REPORT_JSON_PATTERN.match(name):
        return "quality_report_json"
    if REPORT_SUMMARY_MD_PATTERN.match(name):
        return "summary_md"
    if REPORT_SUMMARY_JSON_PATTERN.match(name):
        return "summary_json"
    return None


def list_quality_reports(reports_root: Path) -> list[ReportFileRow]:
    if not reports_root.is_dir():
        return []

    found: list[ReportFileRow] = []
    for path in reports_root.iterdir():
        if not path.is_file():
            continue
        kind = _classify_report_name(path.name)
        if kind is None:
            continue
        found.append(
            ReportFileRow(
                name=path.name,
                path=path,
                kind=kind,
                mtime=path.stat().st_mtime,
            )
        )
    found.sort(key=lambda r: r.mtime, reverse=True)
    return found


def read_quality_report_json(reports_root: Path, filename: str) -> dict[str, Any]:
    text = read_text_under_root(reports_root, filename)
    return json.loads(text)


def read_quality_report_markdown(reports_root: Path, filename: str) -> str:
    return read_text_under_root(reports_root, filename)


def summarize_quality_report(data: dict[str, Any]) -> dict[str, Any]:
    issues = data.get("issues") or []
    issue_codes: dict[str, int] = {}
    for issue in issues:
        if isinstance(issue, dict):
            code = str(issue.get("issue_code") or issue.get("code") or "UNKNOWN")
            issue_codes[code] = issue_codes.get(code, 0) + 1
    return {
        "issue_count": len(issues) if isinstance(issues, list) else data.get("issue_count", 0),
        "issue_codes": issue_codes,
        "report_type": data.get("report_type"),
        "generated_at": data.get("generated_at"),
    }


def inventory_counts(session: Session) -> dict[str, int]:
    file_count = session.execute(select(func.count()).select_from(KbFileInstance)).scalar_one()
    content_count = session.execute(select(func.count()).select_from(KbFileContent)).scalar_one()
    vault_count = session.execute(select(func.count()).select_from(KbRawVaultObject)).scalar_one()
    return {
        "file_instance_count": file_count,
        "file_content_count": content_count,
        "vault_object_count": vault_count,
    }


def vault_status_summary(session: Session) -> list[tuple[str, int]]:
    rows = session.execute(
        select(KbFileContent.vault_status, func.count())
        .group_by(KbFileContent.vault_status)
        .order_by(KbFileContent.vault_status)
    ).all()
    return [(status or "UNKNOWN", count) for status, count in rows]


def file_ext_summary(session: Session, *, limit: int = 20) -> list[tuple[str | None, int]]:
    rows = session.execute(
        select(KbFileInstance.file_ext, func.count())
        .group_by(KbFileInstance.file_ext)
        .order_by(func.count().desc())
        .limit(limit)
    ).all()
    return list(rows)


def list_file_instances(
    session: Session, *, limit: int = 50, offset: int = 0
) -> tuple[list[dict[str, Any]], int]:
    total = session.execute(select(func.count()).select_from(KbFileInstance)).scalar_one()
    rows = session.execute(
        select(KbFileInstance)
        .order_by(KbFileInstance.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).scalars().all()
    items = [
        {
            "file_instance_uid": r.file_instance_uid,
            "source_path": r.source_path,
            "file_name": r.file_name,
            "file_ext": r.file_ext,
            "mime_type": r.mime_type,
            "sha256": r.sha256,
            "content_uid": r.content_uid,
            "status": r.status,
            "is_available": bool(r.is_available),
        }
        for r in rows
    ]
    return items, total


def list_vault_objects_metadata(
    session: Session, *, limit: int = 20
) -> list[dict[str, Any]]:
    rows = session.execute(
        select(KbRawVaultObject)
        .order_by(KbRawVaultObject.created_at.desc())
        .limit(limit)
    ).scalars().all()
    return [
        {
            "vault_uid": r.vault_uid,
            "content_uid": r.content_uid,
            "sha256": r.sha256,
            "vault_path": r.vault_path,
            "copy_status": r.copy_status,
        }
        for r in rows
    ]
