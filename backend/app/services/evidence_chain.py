from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import AppConfig
from app.core.database import create_db_engine, create_session_factory
from app.core.parsed_paths import build_parsed_artifact_paths, build_parsed_content_dir
from app.models.document import KbDocument
from app.models.evidence import KbDocumentChunk, KbEvidence
from app.models.parse_registry import KbParseResult

logger = logging.getLogger(__name__)

REPORT_TYPE = "evidence_build_report"
SCHEMA_VERSION = "1.0"
MODE_BUILD = "build"

ALLOWED_RESULT_STATUSES = frozenset({"SUCCESS", "EMPTY"})
ALLOWED_PARSER_NAMES = frozenset({"markitdown", "mineru"})
QUOTE_TEXT_MAX_LEN = 2000
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

EVIDENCE_TYPE_SECTION_QUOTE = "section_quote"
CHUNK_LEVEL_SECTION = "section"
CHUNK_LEVEL_PAGE = "page"
CHUNK_TYPE_TEXT = "text"


@dataclass
class EvidenceCandidate:
    content_uid: str
    sha256: str
    parser_name: str
    parser_adapter_version: str
    result_status: str
    parsed_dir: str | None
    manifest_path: str | None
    text_path: str | None
    metadata_path: str | None
    document_uid: str


@dataclass
class PlannedChunk:
    chunk_uid: str
    document_uid: str
    content_uid: str
    chunk_index: int
    chunk_type: str
    chunk_level: str
    heading_path: str | None
    page_no: int | None
    slide_no: int | None
    start_offset: int
    end_offset: int
    bbox: dict | None
    content: str
    content_hash: str
    metadata: dict[str, Any] | None = None


@dataclass
class PlannedEvidence:
    evidence_uid: str
    document_uid: str
    content_uid: str
    chunk_uid: str
    evidence_type: str
    source_file_path: str | None
    source_sha256: str
    source_char_start: int
    source_char_end: int
    page_no: int | None
    slide_no: int | None
    heading_path: str | None
    bbox: dict | None
    quote_text: str
    source_location: str
    metadata: dict[str, Any] | None = None


@dataclass
class EvidenceChainBuildResult:
    candidates_selected: int
    documents_processed: int
    documents_skipped: int
    chunks_planned: int = 0
    chunks_upserted: int = 0
    evidence_planned: int = 0
    evidence_upserted: int = 0
    errors: list[str] = field(default_factory=list)
    report_path: Path | None = None


def _utc_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_hex(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _chunk_uid(
    *,
    content_uid: str,
    document_uid: str,
    chunk_index: int,
    content_hash: str,
) -> str:
    payload = f"chunk|v1|{content_uid}|{document_uid}|{chunk_index}|{content_hash}"
    return _sha256_hex(payload)


def _evidence_uid(
    *,
    chunk_uid: str,
    source_char_start: int,
    source_char_end: int,
    evidence_type: str,
) -> str:
    payload = (
        f"evidence|v1|{chunk_uid}|{source_char_start}|{source_char_end}|{evidence_type}"
    )
    return _sha256_hex(payload)


def _truncate_quote(text: str, max_len: int = QUOTE_TEXT_MAX_LEN) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len]


class EvidenceChainService:
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
        content_uid: str | None = None,
        sha256: str | None = None,
        limit: int | None = None,
        dry_run: bool = False,
        force: bool = False,
        output: Path | None = None,
    ) -> EvidenceChainBuildResult:
        if limit is not None and limit < 1:
            raise ValueError("--limit must be >= 1")

        result = EvidenceChainBuildResult(
            candidates_selected=0,
            documents_processed=0,
            documents_skipped=0,
        )

        with self.session_factory() as session:
            if content_uid and sha256:
                self._validate_content_identity(session, content_uid, sha256)

            candidates = self._load_candidates(
                session=session,
                content_uid=content_uid,
                sha256=sha256,
                limit=limit,
            )
            result.candidates_selected = len(candidates)

            for candidate in candidates:
                try:
                    processed = self._process_candidate(
                        session=session,
                        candidate=candidate,
                        dry_run=dry_run,
                        force=force,
                        result=result,
                    )
                    if processed:
                        result.documents_processed += 1
                    else:
                        result.documents_skipped += 1
                except Exception as exc:
                    message = (
                        f"{candidate.content_uid}: unexpected error during evidence build: {exc}"
                    )
                    logger.exception(message)
                    result.errors.append(message)

            if not dry_run:
                session.commit()
            else:
                session.rollback()

        report_path = self._write_report(
            result=result,
            output=output,
            filters={
                "content_uid": content_uid,
                "sha256": sha256,
                "limit": limit,
            },
            dry_run=dry_run,
        )
        result.report_path = report_path
        return result

    def _validate_content_identity(
        self,
        session: Session,
        content_uid: str,
        sha256: str,
    ) -> None:
        query = (
            select(KbParseResult)
            .where(KbParseResult.content_uid == content_uid)
            .where(KbParseResult.sha256 == sha256)
            .limit(1)
        )
        match = session.scalar(query)
        if match is None:
            raise ValueError(
                f"content_uid and sha256 refer to different or missing content: "
                f"{content_uid!r} / {sha256!r}"
            )

    def _load_candidates(
        self,
        *,
        session: Session,
        content_uid: str | None,
        sha256: str | None,
        limit: int | None,
    ) -> list[EvidenceCandidate]:
        query = (
            select(KbParseResult)
            .where(KbParseResult.status.in_(tuple(ALLOWED_RESULT_STATUSES)))
            .order_by(KbParseResult.id.desc())
        )
        if content_uid:
            query = query.where(KbParseResult.content_uid == content_uid)
        if sha256:
            query = query.where(KbParseResult.sha256 == sha256)
        if limit is not None:
            query = query.limit(limit)

        results = session.scalars(query).all()
        candidates: list[EvidenceCandidate] = []
        seen_content: set[str] = set()

        for parse_result in results:
            if parse_result.content_uid in seen_content:
                continue
            seen_content.add(parse_result.content_uid)

            document_uid = self._resolve_document_uid(session, parse_result)
            candidates.append(
                EvidenceCandidate(
                    content_uid=parse_result.content_uid,
                    sha256=parse_result.sha256,
                    parser_name=parse_result.parser_name,
                    parser_adapter_version=parse_result.parser_adapter_version,
                    result_status=parse_result.status,
                    parsed_dir=parse_result.parsed_dir,
                    manifest_path=parse_result.manifest_path,
                    text_path=parse_result.text_path,
                    metadata_path=parse_result.metadata_path,
                    document_uid=document_uid,
                )
            )
        return candidates

    def _resolve_document_uid(
        self,
        session: Session,
        parse_result: KbParseResult,
    ) -> str:
        document = session.scalar(
            select(KbDocument).where(KbDocument.content_uid == parse_result.content_uid)
        )
        if document is not None:
            return document.document_uid
        return parse_result.content_uid

    def _process_candidate(
        self,
        *,
        session: Session,
        candidate: EvidenceCandidate,
        dry_run: bool,
        force: bool,
        result: EvidenceChainBuildResult,
    ) -> bool:
        if not force and self._has_existing_chunks(session, candidate.content_uid):
            logger.info(
                "Skipping %s: evidence chunks already exist (use --force to rebuild)",
                candidate.content_uid,
            )
            return False

        parsed_dir, artifact_paths = self._resolve_artifact_paths(candidate)
        parsed_text_path = artifact_paths["parsed_text"]
        manifest_path = artifact_paths["parse_manifest"]

        if not parsed_text_path.is_file():
            message = (
                f"{candidate.content_uid}: missing parsed_text.md at {parsed_text_path}"
            )
            logger.warning(message)
            result.errors.append(message)
            return False
        if not manifest_path.is_file():
            message = (
                f"{candidate.content_uid}: missing parse_manifest.json at {manifest_path}"
            )
            logger.warning(message)
            result.errors.append(message)
            return False

        manifest = self._load_manifest(manifest_path)
        parser_name = str(manifest.get("parser_name", candidate.parser_name)).lower()
        if parser_name not in ALLOWED_PARSER_NAMES:
            parser_name = candidate.parser_name.lower()

        parsed_text = parsed_text_path.read_text(encoding="utf-8")
        metadata = self._load_metadata(artifact_paths["parsed_metadata"])

        if parser_name == "mineru":
            chunks = self._chunk_mineru(
                candidate=candidate,
                parsed_text=parsed_text,
                metadata=metadata,
                manifest=manifest,
            )
        else:
            chunks = self._chunk_markitdown(
                candidate=candidate,
                parsed_text=parsed_text,
                manifest=manifest,
            )

        if not chunks:
            message = f"{candidate.content_uid}: no chunks planned from parsed_text.md"
            logger.warning(message)
            result.errors.append(message)
            return False

        evidence_items = self._plan_evidence(candidate, chunks, manifest)

        result.chunks_planned += len(chunks)
        result.evidence_planned += len(evidence_items)

        if dry_run:
            return True

        for chunk in chunks:
            self._upsert_chunk(session, chunk)
            result.chunks_upserted += 1
        for evidence in evidence_items:
            self._upsert_evidence(session, evidence)
            result.evidence_upserted += 1
        return True

    def _has_existing_chunks(self, session: Session, content_uid: str) -> bool:
        count = session.scalar(
            select(func.count())
            .select_from(KbDocumentChunk)
            .where(KbDocumentChunk.content_uid == content_uid)
        )
        return bool(count and count > 0)

    def _resolve_artifact_paths(
        self,
        candidate: EvidenceCandidate,
    ) -> tuple[Path, dict[str, Path]]:
        if candidate.parsed_dir:
            parsed_dir = Path(candidate.parsed_dir)
        else:
            parsed_dir = build_parsed_content_dir(
                self.config.storage.parsed_root,
                candidate.sha256,
            )
        artifact_paths = build_parsed_artifact_paths(parsed_dir)
        if candidate.text_path:
            artifact_paths = dict(artifact_paths)
            artifact_paths["parsed_text"] = Path(candidate.text_path)
        if candidate.metadata_path:
            artifact_paths = dict(artifact_paths)
            artifact_paths["parsed_metadata"] = Path(candidate.metadata_path)
        if candidate.manifest_path:
            artifact_paths = dict(artifact_paths)
            artifact_paths["parse_manifest"] = Path(candidate.manifest_path)
        return parsed_dir, artifact_paths

    def _load_manifest(self, manifest_path: Path) -> dict[str, Any]:
        return json.loads(manifest_path.read_text(encoding="utf-8"))

    def _load_metadata(self, metadata_path: Path) -> dict[str, Any]:
        if not metadata_path.is_file():
            return {}
        return json.loads(metadata_path.read_text(encoding="utf-8"))

    def _chunk_markitdown(
        self,
        *,
        candidate: EvidenceCandidate,
        parsed_text: str,
        manifest: dict[str, Any],
    ) -> list[PlannedChunk]:
        del manifest
        sections = self._split_markdown_sections(parsed_text)
        chunks: list[PlannedChunk] = []
        for index, section in enumerate(sections):
            content_hash = _content_hash(section["content"])
            chunk_uid = _chunk_uid(
                content_uid=candidate.content_uid,
                document_uid=candidate.document_uid,
                chunk_index=index,
                content_hash=content_hash,
            )
            chunks.append(
                PlannedChunk(
                    chunk_uid=chunk_uid,
                    document_uid=candidate.document_uid,
                    content_uid=candidate.content_uid,
                    chunk_index=index,
                    chunk_type=CHUNK_TYPE_TEXT,
                    chunk_level=CHUNK_LEVEL_SECTION,
                    heading_path=section["heading_path"],
                    page_no=None,
                    slide_no=None,
                    start_offset=section["start_offset"],
                    end_offset=section["end_offset"],
                    bbox=None,
                    content=section["content"],
                    content_hash=content_hash,
                    metadata={
                        "parser_name": candidate.parser_name,
                        "parser_adapter_version": candidate.parser_adapter_version,
                    },
                )
            )
        return chunks

    def _split_markdown_sections(self, parsed_text: str) -> list[dict[str, Any]]:
        matches = list(HEADING_PATTERN.finditer(parsed_text))
        if not matches:
            content = parsed_text.strip()
            if not content:
                return []
            return [
                {
                    "heading_path": None,
                    "start_offset": 0,
                    "end_offset": len(parsed_text),
                    "content": content,
                }
            ]

        sections: list[dict[str, Any]] = []
        heading_stack: list[tuple[int, str]] = []

        for idx, match in enumerate(matches):
            level = len(match.group(1))
            title = match.group(2).strip()
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, title))
            heading_path = " > ".join(item[1] for item in heading_stack)

            section_start = match.start()
            section_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(parsed_text)
            content = parsed_text[section_start:section_end].strip()
            if not content:
                continue
            sections.append(
                {
                    "heading_path": heading_path,
                    "start_offset": section_start,
                    "end_offset": section_end,
                    "content": content,
                }
            )
        return sections

    def _chunk_mineru(
        self,
        *,
        candidate: EvidenceCandidate,
        parsed_text: str,
        metadata: dict[str, Any],
        manifest: dict[str, Any],
    ) -> list[PlannedChunk]:
        del manifest
        pages = metadata.get("pages")
        if isinstance(pages, list) and pages:
            chunks: list[PlannedChunk] = []
            for index, page in enumerate(pages):
                if not isinstance(page, dict):
                    continue
                start_offset = int(page.get("start_offset", 0))
                end_offset = int(page.get("end_offset", len(parsed_text)))
                end_offset = min(end_offset, len(parsed_text))
                content = parsed_text[start_offset:end_offset].strip()
                if not content:
                    continue
                page_no = page.get("page_no")
                bbox = page.get("bbox")
                if isinstance(bbox, list):
                    bbox = {"coordinates": bbox}
                elif not isinstance(bbox, dict):
                    bbox = None
                content_hash = _content_hash(content)
                chunk_uid = _chunk_uid(
                    content_uid=candidate.content_uid,
                    document_uid=candidate.document_uid,
                    chunk_index=index,
                    content_hash=content_hash,
                )
                chunks.append(
                    PlannedChunk(
                        chunk_uid=chunk_uid,
                        document_uid=candidate.document_uid,
                        content_uid=candidate.content_uid,
                        chunk_index=index,
                        chunk_type=CHUNK_TYPE_TEXT,
                        chunk_level=CHUNK_LEVEL_PAGE,
                        heading_path=None,
                        page_no=int(page_no) if page_no is not None else index + 1,
                        slide_no=None,
                        start_offset=start_offset,
                        end_offset=end_offset,
                        bbox=bbox,
                        content=content,
                        content_hash=content_hash,
                        metadata={
                            "parser_name": candidate.parser_name,
                            "parser_adapter_version": candidate.parser_adapter_version,
                        },
                    )
                )
            if chunks:
                return chunks
        return self._chunk_markitdown(
            candidate=candidate,
            parsed_text=parsed_text,
            manifest={},
        )

    def _plan_evidence(
        self,
        candidate: EvidenceCandidate,
        chunks: list[PlannedChunk],
        manifest: dict[str, Any],
    ) -> list[PlannedEvidence]:
        source_path = manifest.get("parsed_text_path") or manifest.get("source_vault_path")
        if source_path is not None:
            source_path = str(source_path)
        evidence_items: list[PlannedEvidence] = []
        for chunk in chunks:
            quote_text = _truncate_quote(chunk.content)
            source_location = (
                chunk.heading_path
                if chunk.heading_path
                else f"parsed_text.md:{chunk.start_offset}-{chunk.end_offset}"
            )
            evidence_uid = _evidence_uid(
                chunk_uid=chunk.chunk_uid,
                source_char_start=chunk.start_offset,
                source_char_end=chunk.end_offset,
                evidence_type=EVIDENCE_TYPE_SECTION_QUOTE,
            )
            evidence_items.append(
                PlannedEvidence(
                    evidence_uid=evidence_uid,
                    document_uid=candidate.document_uid,
                    content_uid=candidate.content_uid,
                    chunk_uid=chunk.chunk_uid,
                    evidence_type=EVIDENCE_TYPE_SECTION_QUOTE,
                    source_file_path=source_path,
                    source_sha256=candidate.sha256,
                    source_char_start=chunk.start_offset,
                    source_char_end=chunk.end_offset,
                    page_no=chunk.page_no,
                    slide_no=chunk.slide_no,
                    heading_path=chunk.heading_path,
                    bbox=chunk.bbox,
                    quote_text=quote_text,
                    source_location=source_location,
                    metadata={
                        "parser_name": candidate.parser_name,
                        "parser_adapter_version": candidate.parser_adapter_version,
                    },
                )
            )
        return evidence_items

    def _upsert_chunk(self, session: Session, chunk: PlannedChunk) -> None:
        table = KbDocumentChunk.__table__
        values = {
            "chunk_uid": chunk.chunk_uid,
            "document_uid": chunk.document_uid,
            "content_uid": chunk.content_uid,
            "chunk_index": chunk.chunk_index,
            "chunk_type": chunk.chunk_type,
            "chunk_level": chunk.chunk_level,
            "parent_chunk_uid": None,
            "heading_path": chunk.heading_path,
            "page_no": chunk.page_no,
            "slide_no": chunk.slide_no,
            "start_offset": chunk.start_offset,
            "end_offset": chunk.end_offset,
            "bbox": chunk.bbox,
            "content": chunk.content,
            "content_hash": chunk.content_hash,
            "token_count": None,
            "char_count": len(chunk.content),
            "evidence_ref": None,
            "metadata": chunk.metadata,
        }
        stmt = mysql_insert(table).values(**values)
        stmt = stmt.on_duplicate_key_update(
            document_uid=stmt.inserted.document_uid,
            content_uid=stmt.inserted.content_uid,
            chunk_index=stmt.inserted.chunk_index,
            chunk_type=stmt.inserted.chunk_type,
            chunk_level=stmt.inserted.chunk_level,
            heading_path=stmt.inserted.heading_path,
            page_no=stmt.inserted.page_no,
            slide_no=stmt.inserted.slide_no,
            start_offset=stmt.inserted.start_offset,
            end_offset=stmt.inserted.end_offset,
            bbox=stmt.inserted.bbox,
            content=stmt.inserted.content,
            content_hash=stmt.inserted.content_hash,
            char_count=stmt.inserted.char_count,
            metadata=stmt.inserted.metadata,
        )
        session.execute(stmt)

    def _upsert_evidence(self, session: Session, evidence: PlannedEvidence) -> None:
        table = KbEvidence.__table__
        values = {
            "evidence_uid": evidence.evidence_uid,
            "project_uid": None,
            "document_uid": evidence.document_uid,
            "content_uid": evidence.content_uid,
            "chunk_uid": evidence.chunk_uid,
            "evidence_type": evidence.evidence_type,
            "source_file_path": evidence.source_file_path,
            "source_sha256": evidence.source_sha256,
            "source_page_start": evidence.page_no,
            "source_page_end": evidence.page_no,
            "source_char_start": evidence.source_char_start,
            "source_char_end": evidence.source_char_end,
            "page_no": evidence.page_no,
            "slide_no": evidence.slide_no,
            "heading_path": evidence.heading_path,
            "bbox": evidence.bbox,
            "quote_text": evidence.quote_text,
            "normalized_text": None,
            "source_location": evidence.source_location,
            "confidence": None,
            "metadata": evidence.metadata,
        }
        stmt = mysql_insert(table).values(**values)
        stmt = stmt.on_duplicate_key_update(
            document_uid=stmt.inserted.document_uid,
            content_uid=stmt.inserted.content_uid,
            chunk_uid=stmt.inserted.chunk_uid,
            evidence_type=stmt.inserted.evidence_type,
            source_file_path=stmt.inserted.source_file_path,
            source_sha256=stmt.inserted.source_sha256,
            source_page_start=stmt.inserted.source_page_start,
            source_page_end=stmt.inserted.source_page_end,
            source_char_start=stmt.inserted.source_char_start,
            source_char_end=stmt.inserted.source_char_end,
            page_no=stmt.inserted.page_no,
            slide_no=stmt.inserted.slide_no,
            heading_path=stmt.inserted.heading_path,
            bbox=stmt.inserted.bbox,
            quote_text=stmt.inserted.quote_text,
            source_location=stmt.inserted.source_location,
            metadata=stmt.inserted.metadata,
        )
        session.execute(stmt)

    def _write_report(
        self,
        *,
        result: EvidenceChainBuildResult,
        output: Path | None,
        filters: dict[str, Any],
        dry_run: bool,
    ) -> Path | None:
        if output is None:
            return None

        report = {
            "report_type": REPORT_TYPE,
            "schema_version": SCHEMA_VERSION,
            "mode": MODE_BUILD,
            "generated_at": _utc_iso(),
            "dry_run": dry_run,
            "filters": filters,
            "summary": {
                "candidates_selected": result.candidates_selected,
                "documents_processed": result.documents_processed,
                "documents_skipped": result.documents_skipped,
                "chunks_planned": result.chunks_planned,
                "chunks_upserted": result.chunks_upserted,
                "evidence_planned": result.evidence_planned,
                "evidence_upserted": result.evidence_upserted,
                "errors": len(result.errors),
            },
            "errors": result.errors,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return output
