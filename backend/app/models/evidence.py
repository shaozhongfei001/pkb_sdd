from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.file import Base


class KbDocumentChunk(Base):
    __tablename__ = "kb_document_chunk"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    chunk_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    document_uid: Mapped[str] = mapped_column(String(64), nullable=False)
    content_uid: Mapped[str] = mapped_column(String(64), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_type: Mapped[str | None] = mapped_column(String(64))
    chunk_level: Mapped[str | None] = mapped_column(String(32))
    parent_chunk_uid: Mapped[str | None] = mapped_column(String(64))
    heading_path: Mapped[str | None] = mapped_column(Text)
    page_no: Mapped[int | None] = mapped_column(Integer)
    slide_no: Mapped[int | None] = mapped_column(Integer)
    start_offset: Mapped[int | None] = mapped_column(Integer)
    end_offset: Mapped[int | None] = mapped_column(Integer)
    bbox: Mapped[dict | None] = mapped_column(JSON)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    token_count: Mapped[int | None] = mapped_column(Integer)
    char_count: Mapped[int | None] = mapped_column(Integer)
    evidence_ref: Mapped[str | None] = mapped_column(String(256))
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )


class KbEvidence(Base):
    __tablename__ = "kb_evidence"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    evidence_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    project_uid: Mapped[str | None] = mapped_column(String(64))
    document_uid: Mapped[str] = mapped_column(String(64), nullable=False)
    content_uid: Mapped[str] = mapped_column(String(64), nullable=False)
    chunk_uid: Mapped[str | None] = mapped_column(String(64))
    evidence_type: Mapped[str | None] = mapped_column(String(64))
    source_file_path: Mapped[str | None] = mapped_column(Text)
    source_sha256: Mapped[str | None] = mapped_column(String(64))
    source_page_start: Mapped[int | None] = mapped_column(Integer)
    source_page_end: Mapped[int | None] = mapped_column(Integer)
    source_char_start: Mapped[int | None] = mapped_column(Integer)
    source_char_end: Mapped[int | None] = mapped_column(Integer)
    page_no: Mapped[int | None] = mapped_column(Integer)
    slide_no: Mapped[int | None] = mapped_column(Integer)
    heading_path: Mapped[str | None] = mapped_column(Text)
    bbox: Mapped[dict | None] = mapped_column(JSON)
    quote_text: Mapped[str | None] = mapped_column(Text)
    normalized_text: Mapped[str | None] = mapped_column(Text)
    source_location: Mapped[str | None] = mapped_column(String(512))
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
