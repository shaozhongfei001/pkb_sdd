from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import AppConfig
from app.core.database import create_db_engine, create_session_factory
from app.models.document import KbDocument
from app.models.evidence import KbEvidence
from app.models.project import KbCuratedAsset, KbProject, KbProjectDocument

logger = logging.getLogger(__name__)

REPORT_TYPE = "curated_build_report"
SCHEMA_VERSION = "1.0"
MODE_BUILD = "build"
GENERATION_METHOD = "TEMPLATE_RULE"
VERSION_NO = 1
QUOTE_SNIPPET_MAX = 120

MAPPING_MANIFEST = "MANIFEST"
MAPPING_CLI = "CLI"
MAPPING_SEED = "SEED"

ASSET_PROJECT_CARD = "project_card"
ASSET_EVIDENCE_INDEX = "evidence_index"
ASSET_SOURCE_DOCUMENTS = "source_documents"

ASSET_FILES: dict[str, str] = {
    ASSET_PROJECT_CARD: "00_project_card.md",
    ASSET_EVIDENCE_INDEX: "10_evidence_index.md",
    ASSET_SOURCE_DOCUMENTS: "source_documents.md",
}


@dataclass
class DocumentMapping:
    content_uid: str
    document_uid: str
    mapping_method: str


@dataclass
class PlannedAsset:
    asset_type: str
    curated_uid: str
    asset_title: str
    curated_path: str
    file_path: Path
    markdown_body: str
    related_content_uids: list[str]
    related_document_uids: list[str]
    related_evidence_uids: list[str]
    generation_status: str


@dataclass
class CuratedProjectBuildResult:
    project_code: str
    project_uid: str
    documents_mapped: int = 0
    evidence_rows_read: int = 0
    assets_written: int = 0
    assets_skipped: int = 0
    files_written: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    report_path: Path | None = None


def _utc_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_hex(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def normalize_project_code(project_code: str) -> str:
    return project_code.strip()


def project_uid_for(project_code: str) -> str:
    normalized = normalize_project_code(project_code)
    return _sha256_hex(f"project|v1|{normalized}")


def curated_uid_for(project_code: str, asset_type: str, version_no: int = VERSION_NO) -> str:
    normalized = normalize_project_code(project_code)
    return _sha256_hex(f"curated|v1|{normalized}|{asset_type}|{version_no}")


def _truncate_snippet(text: str | None, max_len: int = QUOTE_SNIPPET_MAX) -> str:
    if not text:
        return ""
    text = text.replace("\n", " ").strip()
    if len(text) <= max_len:
        return text
    return text[:max_len] + "…"


class CuratedProjectAssetsService:
    def __init__(
        self,
        config: AppConfig,
        session_factory: sessionmaker[Session] | None = None,
    ) -> None:
        self.config = config
        if session_factory is None:
            engine = create_db_engine(config)
            session_factory = create_session_factory(engine)
        self.session_factory = session_factory

    def build(
        self,
        *,
        project_code: str,
        project_name: str | None = None,
        content_uid: str | None = None,
        manifest_path: Path | None = None,
        limit: int | None = None,
        dry_run: bool = False,
        force: bool = False,
        output: Path | None = None,
    ) -> CuratedProjectBuildResult:
        if limit is not None and limit < 1:
            raise ValueError("--limit must be >= 1")

        normalized_code = normalize_project_code(project_code)
        if not normalized_code:
            raise ValueError("--project-code must not be empty")

        uid = project_uid_for(normalized_code)
        result = CuratedProjectBuildResult(
            project_code=normalized_code,
            project_uid=uid,
        )

        manifest_data: dict[str, Any] | None = None
        if manifest_path is not None:
            manifest_data = self._load_manifest(manifest_path)
            manifest_code = str(manifest_data.get("project_code", "")).strip()
            if manifest_code != normalized_code:
                raise ValueError(
                    f"manifest project_code {manifest_code!r} does not match "
                    f"--project-code {normalized_code!r}"
                )

        with self.session_factory() as session:
            mappings, description = self._resolve_document_mappings(
                session=session,
                project_uid=uid,
                project_code=normalized_code,
                content_uid=content_uid,
                manifest_data=manifest_data,
                limit=limit,
                result=result,
            )
            result.documents_mapped = len(mappings)

            if not mappings:
                raise ValueError(
                    "No documents to curate: provide --manifest, --content-uid, "
                    "or existing kb_project_document rows"
                )

            resolved_name = self._resolve_project_name(
                session=session,
                project_uid=uid,
                project_name=project_name,
                manifest_data=manifest_data,
            )
            if not resolved_name:
                raise ValueError(
                    "--project-name is required when creating a new project without manifest.project_name"
                )

            content_uids = [item.content_uid for item in mappings]
            document_uids = [item.document_uid for item in mappings]
            documents = self._load_documents(session, document_uids)
            evidence_rows = self._load_evidence(session, content_uids)
            result.evidence_rows_read = len(evidence_rows)

            if not evidence_rows:
                result.warnings.append(
                    f"No evidence rows found for project {normalized_code}; "
                    "evidence_index may be empty"
                )

            assets = self._plan_assets(
                project_code=normalized_code,
                project_uid=uid,
                project_name=resolved_name,
                description=description,
                mappings=mappings,
                documents=documents,
                evidence_rows=evidence_rows,
            )

            if dry_run:
                result.assets_written = 0
                result.assets_skipped = len(assets)
                report_assets = [
                    self._asset_report_entry(asset, written=False) for asset in assets
                ]
            else:
                self._upsert_project(
                    session=session,
                    project_uid=uid,
                    project_code=normalized_code,
                    project_name=resolved_name,
                    description=description,
                    document_count=len(mappings),
                )
                for mapping in mappings:
                    self._upsert_project_document(
                        session=session,
                        project_uid=uid,
                        project_code=normalized_code,
                        mapping=mapping,
                    )

                report_assets = []
                for asset in assets:
                    written, skipped = self._write_asset(
                        session=session,
                        asset=asset,
                        project_uid=uid,
                        force=force,
                    )
                    if written:
                        result.assets_written += 1
                        result.files_written += 1
                    if skipped:
                        result.assets_skipped += 1
                    report_assets.append(
                        self._asset_report_entry(asset, written=written and not skipped)
                    )

                session.commit()

            if output is not None:
                result.report_path = self._write_report(
                    result=result,
                    output=output,
                    dry_run=dry_run,
                    manifest_path=manifest_path,
                    content_uid=content_uid,
                    limit=limit,
                    assets=report_assets,
                )

        return result

    def _load_manifest(self, manifest_path: Path) -> dict[str, Any]:
        if not manifest_path.is_file():
            raise FileNotFoundError(f"Manifest not found: {manifest_path}")
        with manifest_path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        if not isinstance(data, dict):
            raise ValueError(f"Manifest must be a YAML mapping: {manifest_path}")
        return data

    def _resolve_document_mappings(
        self,
        *,
        session: Session,
        project_uid: str,
        project_code: str,
        content_uid: str | None,
        manifest_data: dict[str, Any] | None,
        limit: int | None,
        result: CuratedProjectBuildResult,
    ) -> tuple[list[DocumentMapping], str | None]:
        description: str | None = None
        if manifest_data is not None:
            description = manifest_data.get("description")
            raw_docs = manifest_data.get("documents") or []
            if not isinstance(raw_docs, list):
                raise ValueError("manifest.documents must be a list")
            mappings: list[DocumentMapping] = []
            for entry in raw_docs:
                if not isinstance(entry, dict):
                    continue
                entry_content_uid = str(entry.get("content_uid", "")).strip()
                if not entry_content_uid:
                    result.warnings.append("manifest document entry missing content_uid; skipped")
                    continue
                document_uid = str(entry.get("document_uid", "")).strip()
                if not document_uid:
                    document_uid = self._resolve_document_uid(session, entry_content_uid)
                if not document_uid:
                    result.warnings.append(
                        f"No kb_document row for content_uid={entry_content_uid}; skipped"
                    )
                    continue
                mappings.append(
                    DocumentMapping(
                        content_uid=entry_content_uid,
                        document_uid=document_uid,
                        mapping_method=MAPPING_MANIFEST,
                    )
                )
            if limit is not None:
                mappings = mappings[:limit]
            return mappings, description if isinstance(description, str) else None

        if content_uid:
            document_uid = self._resolve_document_uid(session, content_uid)
            if not document_uid:
                raise ValueError(f"No kb_document row for content_uid={content_uid}")
            mappings = [
                DocumentMapping(
                    content_uid=content_uid,
                    document_uid=document_uid,
                    mapping_method=MAPPING_CLI,
                )
            ]
            if limit is not None:
                mappings = mappings[:limit]
            return mappings, None

        seed_rows = session.scalars(
            select(KbProjectDocument)
            .where(KbProjectDocument.project_uid == project_uid)
            .order_by(KbProjectDocument.id.asc())
        ).all()
        if seed_rows:
            mappings = [
                DocumentMapping(
                    content_uid=row.content_uid,
                    document_uid=row.document_uid,
                    mapping_method=MAPPING_SEED,
                )
                for row in seed_rows
            ]
            if limit is not None:
                mappings = mappings[:limit]
            return mappings, None

        return [], None

    def _resolve_document_uid(self, session: Session, content_uid: str) -> str | None:
        document = session.scalar(
            select(KbDocument)
            .where(KbDocument.content_uid == content_uid)
            .order_by(KbDocument.id.desc())
            .limit(1)
        )
        if document is None:
            return None
        return document.document_uid

    def _resolve_project_name(
        self,
        *,
        session: Session,
        project_uid: str,
        project_name: str | None,
        manifest_data: dict[str, Any] | None,
    ) -> str | None:
        if project_name and project_name.strip():
            return project_name.strip()
        if manifest_data is not None:
            manifest_name = manifest_data.get("project_name")
            if isinstance(manifest_name, str) and manifest_name.strip():
                return manifest_name.strip()
        existing = session.scalar(
            select(KbProject).where(KbProject.project_uid == project_uid)
        )
        if existing is not None:
            return existing.project_name
        return None

    def _load_documents(
        self, session: Session, document_uids: list[str]
    ) -> dict[str, KbDocument]:
        if not document_uids:
            return {}
        rows = session.scalars(
            select(KbDocument).where(KbDocument.document_uid.in_(document_uids))
        ).all()
        return {row.document_uid: row for row in rows}

    def _load_evidence(
        self, session: Session, content_uids: list[str]
    ) -> list[KbEvidence]:
        if not content_uids:
            return []
        return list(
            session.scalars(
                select(KbEvidence)
                .where(KbEvidence.content_uid.in_(content_uids))
                .order_by(KbEvidence.id.asc())
            ).all()
        )

    def _plan_assets(
        self,
        *,
        project_code: str,
        project_uid: str,
        project_name: str,
        description: str | None,
        mappings: list[DocumentMapping],
        documents: dict[str, KbDocument],
        evidence_rows: list[KbEvidence],
    ) -> list[PlannedAsset]:
        content_uids = sorted({item.content_uid for item in mappings})
        document_uids = sorted({item.document_uid for item in mappings})
        evidence_uids = sorted({row.evidence_uid for row in evidence_rows})

        project_dir = self.config.storage.curated_root / "projects" / project_code
        assets: list[PlannedAsset] = []

        card_body = self._render_project_card(
            project_code=project_code,
            project_uid=project_uid,
            project_name=project_name,
            description=description,
            document_count=len(mappings),
            content_uids=content_uids,
            document_uids=document_uids,
        )
        card_path = project_dir / ASSET_FILES[ASSET_PROJECT_CARD]
        assets.append(
            PlannedAsset(
                asset_type=ASSET_PROJECT_CARD,
                curated_uid=curated_uid_for(project_code, ASSET_PROJECT_CARD),
                asset_title=f"Project Card: {project_name}",
                curated_path=f"projects/{project_code}/{ASSET_FILES[ASSET_PROJECT_CARD]}",
                file_path=card_path,
                markdown_body=card_body,
                related_content_uids=content_uids,
                related_document_uids=document_uids,
                related_evidence_uids=evidence_uids,
                generation_status="SUCCESS",
            )
        )

        index_body = self._render_evidence_index(
            project_code=project_code,
            evidence_rows=evidence_rows,
        )
        index_path = project_dir / ASSET_FILES[ASSET_EVIDENCE_INDEX]
        assets.append(
            PlannedAsset(
                asset_type=ASSET_EVIDENCE_INDEX,
                curated_uid=curated_uid_for(project_code, ASSET_EVIDENCE_INDEX),
                asset_title=f"Evidence Index: {project_code}",
                curated_path=f"projects/{project_code}/{ASSET_FILES[ASSET_EVIDENCE_INDEX]}",
                file_path=index_path,
                markdown_body=index_body,
                related_content_uids=content_uids,
                related_document_uids=document_uids,
                related_evidence_uids=evidence_uids,
                generation_status="SKIPPED" if not evidence_rows else "SUCCESS",
            )
        )

        source_body = self._render_source_documents(
            project_code=project_code,
            mappings=mappings,
            documents=documents,
        )
        source_path = project_dir / ASSET_FILES[ASSET_SOURCE_DOCUMENTS]
        assets.append(
            PlannedAsset(
                asset_type=ASSET_SOURCE_DOCUMENTS,
                curated_uid=curated_uid_for(project_code, ASSET_SOURCE_DOCUMENTS),
                asset_title=f"Source Documents: {project_code}",
                curated_path=f"projects/{project_code}/{ASSET_FILES[ASSET_SOURCE_DOCUMENTS]}",
                file_path=source_path,
                markdown_body=source_body,
                related_content_uids=content_uids,
                related_document_uids=document_uids,
                related_evidence_uids=evidence_uids,
                generation_status="SUCCESS",
            )
        )
        return assets

    def _render_project_card(
        self,
        *,
        project_code: str,
        project_uid: str,
        project_name: str,
        description: str | None,
        document_count: int,
        content_uids: list[str],
        document_uids: list[str],
    ) -> str:
        lines = [
            f"# Project Card: {project_name}",
            "",
            f"- project_code: `{project_code}`",
            f"- project_uid: `{project_uid}`",
            f"- document_count: {document_count}",
            f"- generation_method: {GENERATION_METHOD}",
            "",
        ]
        if description:
            lines.extend(["## Description", "", description, ""])
        lines.extend(["## Linked content_uids", ""])
        for uid in content_uids:
            lines.append(f"- `{uid}`")
        lines.extend(["", "## Linked document_uids", ""])
        for uid in document_uids:
            lines.append(f"- `{uid}`")
        lines.append("")
        return "\n".join(lines)

    def _render_evidence_index(
        self, *, project_code: str, evidence_rows: list[KbEvidence]
    ) -> str:
        lines = [
            f"# Evidence Index: {project_code}",
            "",
            "| evidence_uid | document_uid | content_uid | page_no | quote_snippet |",
            "|---|---|---|---:|---|",
        ]
        for row in evidence_rows:
            snippet = _truncate_snippet(row.quote_text)
            page_no = "" if row.page_no is None else str(row.page_no)
            lines.append(
                f"| `{row.evidence_uid}` | `{row.document_uid}` | "
                f"`{row.content_uid}` | {page_no} | {snippet} |"
            )
        if not evidence_rows:
            lines.append("| _none_ | | | | |")
        lines.append("")
        return "\n".join(lines)

    def _render_source_documents(
        self,
        *,
        project_code: str,
        mappings: list[DocumentMapping],
        documents: dict[str, KbDocument],
    ) -> str:
        lines = [
            f"# Source Documents: {project_code}",
            "",
            "| document_uid | content_uid | parser_name | title |",
            "|---|---|---|---|",
        ]
        for mapping in mappings:
            document = documents.get(mapping.document_uid)
            parser_name = document.parser_name if document else ""
            title = document.title if document and document.title else ""
            lines.append(
                f"| `{mapping.document_uid}` | `{mapping.content_uid}` | "
                f"{parser_name} | {title} |"
            )
        lines.append("")
        return "\n".join(lines)

    def _write_asset(
        self,
        *,
        session: Session,
        asset: PlannedAsset,
        project_uid: str,
        force: bool,
    ) -> tuple[bool, bool]:
        if self._should_skip_asset(session, asset, force):
            return False, True

        asset.file_path.parent.mkdir(parents=True, exist_ok=True)
        asset.file_path.write_text(asset.markdown_body, encoding="utf-8")
        self._upsert_curated_asset(session=session, project_uid=project_uid, asset=asset)
        return True, False

    def _should_skip_asset(
        self, session: Session, asset: PlannedAsset, force: bool
    ) -> bool:
        if force:
            return False
        existing = session.scalar(
            select(KbCuratedAsset).where(KbCuratedAsset.curated_uid == asset.curated_uid)
        )
        if (
            existing is not None
            and existing.generation_status == "SUCCESS"
            and asset.file_path.is_file()
        ):
            return True
        return False

    def _upsert_project(
        self,
        *,
        session: Session,
        project_uid: str,
        project_code: str,
        project_name: str,
        description: str | None,
        document_count: int,
    ) -> None:
        table = KbProject.__table__
        values = {
            "project_uid": project_uid,
            "project_code": project_code,
            "project_name": project_name,
            "description": description,
            "document_count": document_count,
            "status": "ACTIVE",
        }
        stmt = mysql_insert(table).values(**values)
        stmt = stmt.on_duplicate_key_update(
            project_name=stmt.inserted.project_name,
            description=stmt.inserted.description,
            document_count=stmt.inserted.document_count,
            status=stmt.inserted.status,
        )
        session.execute(stmt)

    def _upsert_project_document(
        self,
        *,
        session: Session,
        project_uid: str,
        project_code: str,
        mapping: DocumentMapping,
    ) -> None:
        table = KbProjectDocument.__table__
        values = {
            "project_uid": project_uid,
            "document_uid": mapping.document_uid,
            "content_uid": mapping.content_uid,
            "confirmed_project_code": project_code,
            "mapping_method": mapping.mapping_method,
            "is_primary": 1,
        }
        stmt = mysql_insert(table).values(**values)
        stmt = stmt.on_duplicate_key_update(
            content_uid=stmt.inserted.content_uid,
            confirmed_project_code=stmt.inserted.confirmed_project_code,
            mapping_method=stmt.inserted.mapping_method,
            is_primary=stmt.inserted.is_primary,
        )
        session.execute(stmt)

    def _upsert_curated_asset(
        self, *, session: Session, project_uid: str, asset: PlannedAsset
    ) -> None:
        table = KbCuratedAsset.__table__
        values = {
            "curated_uid": asset.curated_uid,
            "project_uid": project_uid,
            "asset_type": asset.asset_type,
            "asset_title": asset.asset_title,
            "curated_path": asset.curated_path,
            "related_content_uids": asset.related_content_uids,
            "related_document_uids": asset.related_document_uids,
            "related_evidence_uids": asset.related_evidence_uids,
            "generation_method": GENERATION_METHOD,
            "generation_status": asset.generation_status,
            "version_no": VERSION_NO,
            "metadata": None,
        }
        stmt = mysql_insert(table).values(**values)
        stmt = stmt.on_duplicate_key_update(
            project_uid=stmt.inserted.project_uid,
            asset_type=stmt.inserted.asset_type,
            asset_title=stmt.inserted.asset_title,
            curated_path=stmt.inserted.curated_path,
            related_content_uids=stmt.inserted.related_content_uids,
            related_document_uids=stmt.inserted.related_document_uids,
            related_evidence_uids=stmt.inserted.related_evidence_uids,
            generation_method=stmt.inserted.generation_method,
            generation_status=stmt.inserted.generation_status,
            version_no=stmt.inserted.version_no,
            metadata=stmt.inserted.metadata,
        )
        session.execute(stmt)

    def _asset_report_entry(self, asset: PlannedAsset, *, written: bool) -> dict[str, Any]:
        return {
            "asset_type": asset.asset_type,
            "curated_uid": asset.curated_uid,
            "curated_path": asset.curated_path,
            "generation_method": GENERATION_METHOD,
            "generation_status": asset.generation_status,
            "written": written,
            "related_content_uids": asset.related_content_uids,
            "related_document_uids": asset.related_document_uids,
            "related_evidence_uids": asset.related_evidence_uids,
        }

    def _write_report(
        self,
        *,
        result: CuratedProjectBuildResult,
        output: Path,
        dry_run: bool,
        manifest_path: Path | None,
        content_uid: str | None,
        limit: int | None,
        assets: list[dict[str, Any]],
    ) -> Path:
        payload = {
            "report_type": REPORT_TYPE,
            "schema_version": SCHEMA_VERSION,
            "mode": MODE_BUILD,
            "generated_at": _utc_iso(),
            "dry_run": dry_run,
            "project_code": result.project_code,
            "project_uid": result.project_uid,
            "filters": {
                "content_uid": content_uid,
                "manifest": manifest_path.as_posix() if manifest_path else None,
                "limit": limit,
            },
            "summary": {
                "documents_mapped": result.documents_mapped,
                "evidence_rows_read": result.evidence_rows_read,
                "assets_planned": len(assets),
                "assets_written": result.assets_written,
                "assets_skipped": result.assets_skipped,
                "files_written": result.files_written,
                "db_projects_upserted": 0 if dry_run else 1,
                "db_mappings_upserted": 0 if dry_run else result.documents_mapped,
                "db_assets_upserted": 0 if dry_run else result.assets_written,
                "warnings": len(result.warnings),
                "errors": len(result.errors),
            },
            "assets": assets,
            "warnings": result.warnings,
            "errors": result.errors,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return output
