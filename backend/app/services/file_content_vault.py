from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import AppConfig, ensure_readonly
from app.core.database import create_db_engine, create_session_factory
from app.core.ids import compute_sha256, normalize_path
from app.core.vault_paths import (
    CHUNK_SIZE,
    COPY_COPIED,
    COPY_ERROR,
    VAULT_COPIED,
    VAULT_COPY_ERROR,
    VAULT_NOT_COPIED,
    build_vault_artifact_paths,
    build_vault_dir,
    vault_uid_for,
)
from app.models.file import KbFileContent, KbFileInstance
from app.models.vault import KbRawVaultObject

logger = logging.getLogger(__name__)

STATUS_CONTENT_REGISTERED = "CONTENT_REGISTERED"
STATUS_DISCOVERED = "DISCOVERED"


@dataclass
class VaultCopyError:
    content_uid: str
    sha256: str
    message: str


@dataclass
class VaultCopyResult:
    candidates: int = 0
    copied: int = 0
    skipped: int = 0
    metadata_refreshed: int = 0
    errors: list[VaultCopyError] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "candidates": self.candidates,
            "copied": self.copied,
            "skipped": self.skipped,
            "metadata_refreshed": self.metadata_refreshed,
            "errors": [
                {
                    "content_uid": item.content_uid,
                    "sha256": item.sha256,
                    "message": item.message,
                }
                for item in self.errors
            ],
        }


class FileContentVaultService:
    def __init__(self, config: AppConfig) -> None:
        ensure_readonly(config)
        self.config = config
        engine = create_db_engine(config)
        self.session_factory = create_session_factory(engine)

    def copy_to_vault(
        self,
        limit: int | None = None,
        sha256: str | None = None,
        content_uid: str | None = None,
        refresh_metadata_only: bool = False,
    ) -> VaultCopyResult:
        result = VaultCopyResult()
        contents = self._load_candidates(
            sha256=sha256,
            content_uid=content_uid,
            refresh_metadata_only=refresh_metadata_only,
            limit=limit,
        )
        result.candidates = len(contents)

        for content in contents:
            self._process_content(
                content=content,
                result=result,
                refresh_metadata_only=refresh_metadata_only,
            )

        return result

    def _load_candidates(
        self,
        sha256: str | None,
        content_uid: str | None,
        refresh_metadata_only: bool,
        limit: int | None,
    ) -> list[KbFileContent]:
        target_sha = sha256 or content_uid
        with self.session_factory() as session:
            query = select(KbFileContent).where(
                KbFileContent.sha256.isnot(None),
                KbFileContent.status == STATUS_CONTENT_REGISTERED,
            )
            if target_sha:
                query = query.where(KbFileContent.sha256 == target_sha)
            elif refresh_metadata_only:
                query = query.where(KbFileContent.vault_status == VAULT_COPIED)
            else:
                query = query.where(KbFileContent.vault_status == VAULT_NOT_COPIED)

            query = query.order_by(KbFileContent.id.asc())
            if limit is not None:
                query = query.limit(limit)
            return list(session.scalars(query).all())

    def _process_content(
        self,
        content: KbFileContent,
        result: VaultCopyResult,
        refresh_metadata_only: bool,
    ) -> None:
        sha256 = content.sha256
        content_uid = content.content_uid
        assert sha256 is not None

        try:
            with self.session_factory() as session:
                db_content = session.scalar(
                    select(KbFileContent).where(KbFileContent.sha256 == sha256)
                )
                if db_content is None:
                    raise RuntimeError(f"Content not found for sha256={sha256}")

                instances = list(
                    session.scalars(
                        select(KbFileInstance)
                        .where(KbFileInstance.sha256 == sha256)
                        .order_by(
                            KbFileInstance.created_at.asc(),
                            KbFileInstance.id.asc(),
                        )
                    ).all()
                )
                if not instances:
                    raise RuntimeError(f"No file instances found for sha256={sha256}")

                copy_source, master_instance = self._resolve_copy_source(
                    session, db_content, instances
                )
                vault_dir = build_vault_dir(self.config.storage.raw_vault_root, sha256)
                artifacts = build_vault_artifact_paths(vault_dir)
                copied_at = datetime.now(UTC).replace(tzinfo=None)

                bin_exists = artifacts["original_bin"].is_file()
                bin_valid = (
                    bin_exists and compute_sha256(artifacts["original_bin"]) == sha256
                )

                if refresh_metadata_only and not bin_valid:
                    raise RuntimeError(
                        "refresh-metadata-only requires a valid existing original.bin"
                    )

                did_copy = False
                if bin_valid:
                    result.skipped += 1
                else:
                    vault_dir.mkdir(parents=True, exist_ok=True)
                    self._copy_file_chunked(copy_source, artifacts["original_bin"])
                    actual_hash = compute_sha256(artifacts["original_bin"])
                    if actual_hash != sha256:
                        raise RuntimeError(
                            f"Vault copy hash mismatch: expected={sha256} actual={actual_hash}"
                        )
                    did_copy = True
                    result.copied += 1

                result.metadata_refreshed += 1

                self._write_sidecar_files(
                    artifacts=artifacts,
                    content=db_content,
                    instances=instances,
                    master_instance=master_instance,
                    copy_source=copy_source,
                    vault_status=VAULT_COPIED,
                    copied_at=copied_at,
                )

                db_content.vault_path = vault_dir.as_posix()
                db_content.vault_status = VAULT_COPIED
                self._upsert_vault_object(
                    session=session,
                    content=db_content,
                    artifacts=artifacts,
                    master_instance=master_instance,
                    copy_status=COPY_COPIED,
                    copied_at=copied_at,
                    error_message=None,
                )
                session.commit()

                logger.info(
                    "Vault copy completed sha256=%s copied=%s vault_dir=%s",
                    sha256,
                    did_copy,
                    vault_dir,
                )
        except Exception as exc:
            logger.exception("Vault copy failed for sha256=%s", sha256)
            result.errors.append(
                VaultCopyError(
                    content_uid=content_uid,
                    sha256=sha256,
                    message=str(exc),
                )
            )
            self._record_copy_error(content_uid=content_uid, sha256=sha256, message=str(exc))

    def _resolve_copy_source(
        self,
        session: Session,
        content: KbFileContent,
        instances: list[KbFileInstance],
    ) -> tuple[Path, KbFileInstance]:
        ordered: list[KbFileInstance] = []
        if content.master_file_instance_uid:
            master = session.scalar(
                select(KbFileInstance).where(
                    KbFileInstance.file_instance_uid == content.master_file_instance_uid
                )
            )
            if master is not None:
                ordered.append(master)

        for instance in instances:
            if instance not in ordered:
                ordered.append(instance)

        for instance in ordered:
            if instance.status != STATUS_DISCOVERED:
                continue
            source_path = Path(instance.source_path)
            if self._is_readable_source(source_path):
                return normalize_path(source_path), instance

        raise RuntimeError("No readable source path found for content")

    def _is_readable_source(self, path: Path) -> bool:
        if not path.is_file():
            return False
        try:
            with path.open("rb") as handle:
                handle.read(1)
            return True
        except OSError:
            return False

    def _copy_file_chunked(self, source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with source.open("rb") as src, destination.open("wb") as dst:
            while True:
                chunk = src.read(CHUNK_SIZE)
                if not chunk:
                    break
                dst.write(chunk)

    def _write_sidecar_files(
        self,
        artifacts: dict[str, Path],
        content: KbFileContent,
        instances: list[KbFileInstance],
        master_instance: KbFileInstance,
        copy_source: Path,
        vault_status: str,
        copied_at: datetime,
    ) -> None:
        sha256 = content.sha256
        assert sha256 is not None

        source_paths_payload = {
            "content_uid": content.content_uid,
            "sha256": sha256,
            "instance_count": content.instance_count,
            "master_file_instance_uid": content.master_file_instance_uid,
            "generated_at": copied_at.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z"),
            "instances": [
                {
                    "file_instance_uid": item.file_instance_uid,
                    "source_path": item.source_path,
                    "file_name": item.file_name,
                    "file_ext": item.file_ext,
                    "source_root": item.source_root,
                    "is_duplicate_instance": item.is_duplicate_instance,
                    "status": item.status,
                }
                for item in instances
            ],
        }
        metadata_payload = {
            "content_uid": content.content_uid,
            "sha256": sha256,
            "file_size": content.file_size,
            "file_ext": content.file_ext,
            "mime_type": content.mime_type,
            "instance_count": content.instance_count,
            "master_file_instance_uid": content.master_file_instance_uid,
            "master_source_path": master_instance.source_path,
            "master_file_name": master_instance.file_name,
            "vault_path": artifacts["vault_dir"].as_posix(),
            "copy_source_path": copy_source.as_posix(),
            "vault_status": vault_status,
            "pipeline_version": self.config.pipeline_version,
            "copied_at": copied_at.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z"),
        }

        artifacts["vault_dir"].mkdir(parents=True, exist_ok=True)
        artifacts["original_name"].write_text(master_instance.file_name, encoding="utf-8")
        artifacts["source_paths_json"].write_text(
            json.dumps(source_paths_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        artifacts["file_metadata_json"].write_text(
            json.dumps(metadata_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _upsert_vault_object(
        self,
        session: Session,
        content: KbFileContent,
        artifacts: dict[str, Path],
        master_instance: KbFileInstance,
        copy_status: str,
        copied_at: datetime | None,
        error_message: str | None,
    ) -> None:
        sha256 = content.sha256
        assert sha256 is not None
        vault_object = session.scalar(
            select(KbRawVaultObject).where(KbRawVaultObject.sha256 == sha256)
        )
        if vault_object is None:
            vault_object = KbRawVaultObject(
                vault_uid=vault_uid_for(sha256),
                content_uid=content.content_uid,
                sha256=sha256,
                vault_path=artifacts["vault_dir"].as_posix(),
                original_name=master_instance.file_name,
                source_paths_json_path=artifacts["source_paths_json"].as_posix(),
                file_metadata_json_path=artifacts["file_metadata_json"].as_posix(),
                copy_status=copy_status,
                copied_at=copied_at,
                error_message=error_message,
            )
            session.add(vault_object)
            return

        vault_object.vault_path = artifacts["vault_dir"].as_posix()
        vault_object.original_name = master_instance.file_name
        vault_object.source_paths_json_path = artifacts["source_paths_json"].as_posix()
        vault_object.file_metadata_json_path = artifacts["file_metadata_json"].as_posix()
        vault_object.copy_status = copy_status
        vault_object.copied_at = copied_at
        vault_object.error_message = error_message

    def _record_copy_error(
        self,
        content_uid: str,
        sha256: str,
        message: str,
    ) -> None:
        try:
            with self.session_factory() as session:
                content = session.scalar(
                    select(KbFileContent).where(KbFileContent.sha256 == sha256)
                )
                if content is not None:
                    content.vault_status = VAULT_COPY_ERROR

                vault_object = session.scalar(
                    select(KbRawVaultObject).where(KbRawVaultObject.sha256 == sha256)
                )
                if vault_object is None:
                    vault_object = KbRawVaultObject(
                        vault_uid=vault_uid_for(sha256),
                        content_uid=content_uid,
                        sha256=sha256,
                        vault_path="",
                        copy_status=COPY_ERROR,
                        error_message=message,
                    )
                    session.add(vault_object)
                else:
                    vault_object.copy_status = COPY_ERROR
                    vault_object.error_message = message
                session.commit()
        except Exception:
            logger.exception("Failed to record vault copy error sha256=%s", sha256)
