from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.mysql import JSON, TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from app.models.file import Base


class KbProject(Base):
    __tablename__ = "kb_project"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    project_code: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    project_name: Mapped[str] = mapped_column(String(512), nullable=False)
    client_name: Mapped[str | None] = mapped_column(String(512))
    domain: Mapped[str | None] = mapped_column(String(256))
    project_type: Mapped[str | None] = mapped_column(String(128))
    year_start: Mapped[int | None] = mapped_column(Integer)
    year_end: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    aliases: Mapped[dict | list | None] = mapped_column(JSON)
    keywords: Mapped[dict | list | None] = mapped_column(JSON)
    document_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    core_document_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    completeness_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    has_requirement_doc: Mapped[int | None] = mapped_column(TINYINT, server_default="0")
    has_solution_doc: Mapped[int | None] = mapped_column(TINYINT, server_default="0")
    has_design_doc: Mapped[int | None] = mapped_column(TINYINT, server_default="0")
    has_delivery_doc: Mapped[int | None] = mapped_column(TINYINT, server_default="0")
    has_acceptance_doc: Mapped[int | None] = mapped_column(TINYINT, server_default="0")
    has_training_doc: Mapped[int | None] = mapped_column(TINYINT, server_default="0")
    value_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    status: Mapped[str] = mapped_column(String(64), nullable=False, server_default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class KbProjectDocument(Base):
    __tablename__ = "kb_project_document"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_uid: Mapped[str] = mapped_column(String(64), nullable=False)
    document_uid: Mapped[str] = mapped_column(String(64), nullable=False)
    content_uid: Mapped[str] = mapped_column(String(64), nullable=False)
    candidate_project_code: Mapped[str | None] = mapped_column(String(128))
    candidate_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    confirmed_project_code: Mapped[str | None] = mapped_column(String(128))
    confirmed_by: Mapped[str | None] = mapped_column(String(128))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    mapping_method: Mapped[str | None] = mapped_column(String(64))
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    is_primary: Mapped[int] = mapped_column(TINYINT, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )


class KbCuratedAsset(Base):
    __tablename__ = "kb_curated_asset"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    curated_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    project_uid: Mapped[str | None] = mapped_column(String(64))
    asset_type: Mapped[str] = mapped_column(String(64), nullable=False)
    asset_title: Mapped[str | None] = mapped_column(String(1024))
    curated_path: Mapped[str] = mapped_column(Text, nullable=False)
    related_content_uids: Mapped[list | None] = mapped_column(JSON)
    related_document_uids: Mapped[list | None] = mapped_column(JSON)
    related_evidence_uids: Mapped[list | None] = mapped_column(JSON)
    generation_method: Mapped[str | None] = mapped_column(String(64))
    generation_status: Mapped[str | None] = mapped_column(String(64))
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
