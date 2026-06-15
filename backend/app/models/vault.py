from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.file import Base


class KbRawVaultObject(Base):
    __tablename__ = "kb_raw_vault_object"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    vault_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    content_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    vault_path: Mapped[str] = mapped_column(Text, nullable=False)
    original_name: Mapped[str | None] = mapped_column(String(512))
    source_paths_json_path: Mapped[str | None] = mapped_column(Text)
    file_metadata_json_path: Mapped[str | None] = mapped_column(Text)
    copy_status: Mapped[str] = mapped_column(String(64), nullable=False, default="PENDING")
    copied_at: Mapped[datetime | None] = mapped_column(DateTime)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
