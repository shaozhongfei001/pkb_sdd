from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.file import Base


class KbDuplicateGroup(Base):
    __tablename__ = "kb_duplicate_group"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    duplicate_group_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    content_uid: Mapped[str] = mapped_column(String(64), nullable=False)
    instance_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    master_file_instance_uid: Mapped[str | None] = mapped_column(String(64))
    decision: Mapped[str] = mapped_column(String(64), nullable=False, default="PENDING")
    decision_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
