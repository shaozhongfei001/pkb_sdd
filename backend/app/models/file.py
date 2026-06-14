from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.mysql import JSON, TINYINT
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class KbFileInstance(Base):
    __tablename__ = "kb_file_instance"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    file_instance_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    source_path_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    file_name: Mapped[str] = mapped_column(String(512), nullable=False)
    file_ext: Mapped[str | None] = mapped_column(String(32))
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    mime_type: Mapped[str | None] = mapped_column(String(128))
    created_time: Mapped[datetime | None] = mapped_column(DateTime)
    modified_time: Mapped[datetime | None] = mapped_column(DateTime)
    content_uid: Mapped[str | None] = mapped_column(String(64))
    sha256: Mapped[str | None] = mapped_column(String(64))
    source_device: Mapped[str | None] = mapped_column(String(256))
    source_root: Mapped[str | None] = mapped_column(Text)
    is_available: Mapped[int] = mapped_column(TINYINT, nullable=False, default=1)
    is_duplicate_instance: Mapped[int] = mapped_column(TINYINT, nullable=False, default=0)
    duplicate_group_uid: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="DISCOVERED")
    error_message: Mapped[str | None] = mapped_column(Text)
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


class KbFileContent(Base):
    __tablename__ = "kb_file_content"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    content_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    file_ext: Mapped[str | None] = mapped_column(String(32))
    mime_type: Mapped[str | None] = mapped_column(String(128))
    master_file_instance_uid: Mapped[str | None] = mapped_column(String(64))
    instance_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    vault_path: Mapped[str | None] = mapped_column(Text)
    vault_status: Mapped[str] = mapped_column(String(64), nullable=False, default="NOT_COPIED")
    value_level: Mapped[str | None] = mapped_column(String(8))
    value_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    value_reason: Mapped[str | None] = mapped_column(Text)
    candidate_project_code: Mapped[str | None] = mapped_column(String(128))
    parse_status: Mapped[str | None] = mapped_column(String(64))
    quality_status: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="CONTENT_REGISTERED")
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
