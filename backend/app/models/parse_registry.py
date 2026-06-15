from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.mysql import JSON, TINYINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.file import Base


class KbParseRun(Base):
    __tablename__ = "kb_parse_run"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    parser_name: Mapped[str] = mapped_column(String(64), nullable=False)
    parser_adapter_version: Mapped[str] = mapped_column(String(128), nullable=False)
    parser_family: Mapped[str] = mapped_column(
        String(64), nullable=False, default="MARKITDOWN_FAMILY"
    )
    trigger_type: Mapped[str] = mapped_column(
        String(64), nullable=False, default="REGISTER_REPORT"
    )
    filters_json: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="PENDING")
    dry_run: Mapped[int] = mapped_column(TINYINT, nullable=False, default=0)
    total_candidates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    in_scope_candidates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parsed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    empty_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    report_path: Mapped[str | None] = mapped_column(Text)
    registry_report_path: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
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

    results: Mapped[list["KbParseResult"]] = relationship(
        "KbParseResult",
        back_populates="run",
        foreign_keys="KbParseResult.run_uid",
        primaryjoin="KbParseRun.run_uid == KbParseResult.run_uid",
    )


class KbParseResult(Base):
    __tablename__ = "kb_parse_result"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    result_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    run_uid: Mapped[str] = mapped_column(
        String(64), ForeignKey("kb_parse_run.run_uid"), nullable=False
    )
    content_uid: Mapped[str] = mapped_column(String(64), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    route_type: Mapped[str | None] = mapped_column(String(64))
    decision: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    source_vault_path: Mapped[str | None] = mapped_column(Text)
    parsed_dir: Mapped[str | None] = mapped_column(Text)
    manifest_path: Mapped[str | None] = mapped_column(Text)
    metadata_path: Mapped[str | None] = mapped_column(Text)
    text_path: Mapped[str | None] = mapped_column(Text)
    output_hash: Mapped[str | None] = mapped_column(String(64))
    output_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    error_code: Mapped[str | None] = mapped_column(String(128))
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_of_result_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("kb_parse_result.id")
    )
    parser_name: Mapped[str] = mapped_column(String(64), nullable=False)
    parser_adapter_version: Mapped[str] = mapped_column(String(128), nullable=False)
    pipeline_version: Mapped[str] = mapped_column(String(64), nullable=False, default="v1.1")
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

    run: Mapped["KbParseRun"] = relationship(
        "KbParseRun",
        back_populates="results",
        foreign_keys=[run_uid],
    )
    retry_of: Mapped["KbParseResult | None"] = relationship(
        "KbParseResult",
        remote_side="KbParseResult.id",
        foreign_keys=[retry_of_result_id],
    )


class KbParsedArtifact(Base):
    __tablename__ = "kb_parsed_artifact"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    artifact_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    run_uid: Mapped[str] = mapped_column(
        String(64), ForeignKey("kb_parse_run.run_uid"), nullable=False
    )
    content_uid: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    sha256: Mapped[str | None] = mapped_column(String(64))
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_path: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_hash: Mapped[str | None] = mapped_column(String(64))
    artifact_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    parser_name: Mapped[str] = mapped_column(String(64), nullable=False)
    parser_adapter_version: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="INDEXED")
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

    run: Mapped["KbParseRun"] = relationship(
        "KbParseRun",
        foreign_keys=[run_uid],
    )
