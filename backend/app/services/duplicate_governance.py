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
from app.models.duplicate import KbDuplicateGroup
from app.models.file import KbFileContent, KbFileInstance
from app.models.vault import KbRawVaultObject

logger = logging.getLogger(__name__)

STATUS_CONTENT_REGISTERED = "CONTENT_REGISTERED"
STATUS_DISCOVERED = "DISCOVERED"
DECISION_PENDING = "PENDING"
SUGGESTED_ACTION_REVIEW_DUPLICATE = "REVIEW_DUPLICATE"

DUPLICATE_NAME_MARKERS = ("副本", "copy", "bak", "tmp", "临时", "- copy", "_copy")


@dataclass
class GovernError:
    sha256: str
    message: str


@dataclass
class DuplicateGovernanceResult:
    candidates: int = 0
    groups_processed: int = 0
    groups_upserted: int = 0
    instances_linked: int = 0
    suggestions_generated: int = 0
    skipped: int = 0
    errors: list[GovernError] = field(default_factory=list)
    duplicate_report_path: Path | None = None
    cleanup_suggestion_report_path: Path | None = None

    def to_dict(self) -> dict:
        return {
            "candidates": self.candidates,
            "groups_processed": self.groups_processed,
            "groups_upserted": self.groups_upserted,
            "instances_linked": self.instances_linked,
            "suggestions_generated": self.suggestions_generated,
            "skipped": self.skipped,
            "errors": [
                {"sha256": item.sha256, "message": item.message} for item in self.errors
            ],
            "duplicate_report_path": (
                self.duplicate_report_path.as_posix()
                if self.duplicate_report_path is not None
                else None
            ),
            "cleanup_suggestion_report_path": (
                self.cleanup_suggestion_report_path.as_posix()
                if self.cleanup_suggestion_report_path is not None
                else None
            ),
        }


def is_copy_like_filename(file_name: str) -> bool:
    lowered = file_name.lower()
    return any(marker in lowered for marker in DUPLICATE_NAME_MARKERS)


def select_master_candidate(instances: list[KbFileInstance]) -> KbFileInstance:
    if not instances:
        raise ValueError("Cannot select master from empty instance list")

    def sort_key(instance: KbFileInstance) -> tuple:
        modified = instance.modified_time or datetime.max
        created = instance.created_at or datetime.max
        return (
            instance.is_duplicate_instance,
            len(instance.source_path),
            is_copy_like_filename(instance.file_name),
            modified,
            created,
            instance.file_instance_uid,
        )

    return min(instances, key=sort_key)


class DuplicateGovernanceService:
    def __init__(self, config: AppConfig) -> None:
        ensure_readonly(config)
        self.config = config
        engine = create_db_engine(config)
        self.session_factory = create_session_factory(engine)

    def govern_duplicates(
        self,
        limit: int | None = None,
        sha256: str | None = None,
        content_uid: str | None = None,
    ) -> DuplicateGovernanceResult:
        result = DuplicateGovernanceResult()
        contents = self._load_candidates(
            sha256=sha256,
            content_uid=content_uid,
            limit=limit,
        )
        result.candidates = len(contents)

        group_entries: list[dict] = []
        suggestions: list[dict] = []

        for content in contents:
            result.groups_processed += 1
            try:
                group_entry, group_suggestions, upserted, linked, skipped = self._govern_content(
                    content
                )
                if group_entry is None:
                    continue
                group_entries.append(group_entry)
                suggestions.extend(group_suggestions)
                result.suggestions_generated += len(group_suggestions)
                result.instances_linked += linked
                if upserted:
                    result.groups_upserted += 1
                elif skipped:
                    result.skipped += 1
            except Exception as exc:
                logger.exception("Duplicate governance failed for sha256=%s", content.sha256)
                result.errors.append(
                    GovernError(sha256=content.sha256, message=str(exc))
                )

        duplicate_path, cleanup_path = self._write_reports(
            result=result,
            groups=group_entries,
            suggestions=suggestions,
        )
        result.duplicate_report_path = duplicate_path
        result.cleanup_suggestion_report_path = cleanup_path
        return result

    def _load_candidates(
        self,
        sha256: str | None,
        content_uid: str | None,
        limit: int | None,
    ) -> list[KbFileContent]:
        target_sha = sha256 or content_uid
        with self.session_factory() as session:
            query = select(KbFileContent).where(
                KbFileContent.sha256.isnot(None),
                KbFileContent.instance_count >= 2,
                KbFileContent.status == STATUS_CONTENT_REGISTERED,
            )
            if target_sha:
                query = query.where(KbFileContent.sha256 == target_sha)
            query = query.order_by(KbFileContent.id.asc())
            if limit is not None:
                query = query.limit(limit)
            return list(session.scalars(query).all())

    def _govern_content(
        self,
        content: KbFileContent,
    ) -> tuple[dict | None, list[dict], bool, int, bool]:
        sha256 = content.sha256
        assert sha256 is not None
        duplicate_group_uid = sha256

        with self.session_factory() as session:
            db_content = session.scalar(
                select(KbFileContent).where(KbFileContent.sha256 == sha256)
            )
            if db_content is None:
                raise RuntimeError(f"Content not found for sha256={sha256}")

            instances = list(
                session.scalars(
                    select(KbFileInstance)
                    .where(
                        KbFileInstance.sha256 == sha256,
                        KbFileInstance.status == STATUS_DISCOVERED,
                    )
                    .order_by(
                        KbFileInstance.created_at.asc(),
                        KbFileInstance.id.asc(),
                    )
                ).all()
            )

            if len(instances) < 2:
                logger.warning(
                    "Skipping duplicate group sha256=%s: found %s instances (expected >= 2)",
                    sha256,
                    len(instances),
                )
                return None, [], False, 0, False

            if db_content.instance_count != len(instances):
                logger.warning(
                    "instance_count mismatch sha256=%s db=%s actual=%s",
                    sha256,
                    db_content.instance_count,
                    len(instances),
                )

            master = select_master_candidate(instances)
            vault_path = self._resolve_vault_path(session, db_content)

            upserted, skipped = self._upsert_duplicate_group(
                session=session,
                duplicate_group_uid=duplicate_group_uid,
                sha256=sha256,
                content_uid=db_content.content_uid,
                instance_count=len(instances),
                master_file_instance_uid=master.file_instance_uid,
            )

            linked = self._link_instances(session, instances, duplicate_group_uid)
            session.commit()

            group_entry = self._build_group_entry(
                duplicate_group_uid=duplicate_group_uid,
                sha256=sha256,
                content_uid=db_content.content_uid,
                instance_count=len(instances),
                master=master,
                instances=instances,
                vault_path=vault_path,
            )
            group_suggestions = build_cleanup_suggestions(
                duplicate_group_uid=duplicate_group_uid,
                sha256=sha256,
                content_uid=db_content.content_uid,
                master=master,
                instances=instances,
                vault_path=vault_path,
                content_master_file_instance_uid=db_content.master_file_instance_uid,
            )

            logger.info(
                "Duplicate group processed sha256=%s master=%s instances=%s upserted=%s skipped=%s",
                sha256,
                master.file_instance_uid,
                len(instances),
                upserted,
                skipped,
            )
            return group_entry, group_suggestions, upserted, linked, skipped

    def _resolve_vault_path(
        self,
        session: Session,
        content: KbFileContent,
    ) -> str | None:
        if content.vault_path:
            return content.vault_path
        vault_object = session.scalar(
            select(KbRawVaultObject).where(KbRawVaultObject.sha256 == content.sha256)
        )
        if vault_object is not None:
            return vault_object.vault_path
        return None

    def _upsert_duplicate_group(
        self,
        session: Session,
        duplicate_group_uid: str,
        sha256: str,
        content_uid: str,
        instance_count: int,
        master_file_instance_uid: str,
    ) -> tuple[bool, bool]:
        group = session.scalar(
            select(KbDuplicateGroup).where(
                KbDuplicateGroup.duplicate_group_uid == duplicate_group_uid
            )
        )
        desired = {
            "sha256": sha256,
            "content_uid": content_uid,
            "instance_count": instance_count,
            "master_file_instance_uid": master_file_instance_uid,
            "decision": DECISION_PENDING,
        }

        if group is None:
            group = KbDuplicateGroup(
                duplicate_group_uid=duplicate_group_uid,
                sha256=sha256,
                content_uid=content_uid,
                instance_count=instance_count,
                master_file_instance_uid=master_file_instance_uid,
                decision=DECISION_PENDING,
                decision_reason=None,
            )
            session.add(group)
            return True, False

        unchanged = all(getattr(group, key) == value for key, value in desired.items())
        if unchanged:
            return False, True

        group.sha256 = sha256
        group.content_uid = content_uid
        group.instance_count = instance_count
        group.master_file_instance_uid = master_file_instance_uid
        group.decision = DECISION_PENDING
        return True, False

    def _link_instances(
        self,
        session: Session,
        instances: list[KbFileInstance],
        duplicate_group_uid: str,
    ) -> int:
        linked = 0
        for instance in instances:
            if instance.duplicate_group_uid != duplicate_group_uid:
                instance.duplicate_group_uid = duplicate_group_uid
                linked += 1
        return linked

    def _build_group_entry(
        self,
        duplicate_group_uid: str,
        sha256: str,
        content_uid: str,
        instance_count: int,
        master: KbFileInstance,
        instances: list[KbFileInstance],
        vault_path: str | None,
    ) -> dict:
        return {
            "duplicate_group_uid": duplicate_group_uid,
            "sha256": sha256,
            "content_uid": content_uid,
            "instance_count": instance_count,
            "master_file_instance_uid": master.file_instance_uid,
            "master_source_path": master.source_path,
            "decision": DECISION_PENDING,
            "vault_path": vault_path,
            "instances": [
                {
                    "file_instance_uid": item.file_instance_uid,
                    "source_path": item.source_path,
                    "file_name": item.file_name,
                    "is_duplicate_instance": item.is_duplicate_instance,
                    "duplicate_group_uid": duplicate_group_uid,
                }
                for item in instances
            ],
        }

    def _write_reports(
        self,
        result: DuplicateGovernanceResult,
        groups: list[dict],
        suggestions: list[dict],
    ) -> tuple[Path | None, Path | None]:
        reports_root = self.config.storage.reports_root
        reports_root.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        generated_at = datetime.now(UTC).replace(tzinfo=UTC).isoformat().replace("+00:00", "Z")

        duplicate_report_path = reports_root / f"duplicate_report_{timestamp}.json"
        cleanup_report_path = reports_root / f"cleanup_suggestion_report_{timestamp}.json"

        duplicate_payload = {
            "report_type": "duplicate_report",
            "pipeline_version": self.config.pipeline_version,
            "generated_at": generated_at,
            "summary": {
                "candidates": result.candidates,
                "groups_processed": result.groups_processed,
                "groups_upserted": result.groups_upserted,
                "instances_linked": result.instances_linked,
                "errors": len(result.errors),
            },
            "groups": groups,
            "errors": [
                {"sha256": item.sha256, "message": item.message} for item in result.errors
            ],
        }
        cleanup_payload = {
            "report_type": "cleanup_suggestion_report",
            "pipeline_version": self.config.pipeline_version,
            "generated_at": generated_at,
            "auto_execute": False,
            "summary": {
                "suggestions_generated": len(suggestions),
                "groups_with_suggestions": len(
                    {item["duplicate_group_uid"] for item in suggestions}
                ),
            },
            "suggestions": suggestions,
        }

        try:
            duplicate_report_path.write_text(
                json.dumps(duplicate_payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            cleanup_report_path.write_text(
                json.dumps(cleanup_payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            logger.info("Wrote duplicate report: %s", duplicate_report_path)
            logger.info("Wrote cleanup suggestion report: %s", cleanup_report_path)
            return duplicate_report_path, cleanup_report_path
        except Exception as exc:
            logger.exception("Failed to write duplicate governance reports")
            result.errors.append(GovernError(sha256="", message=f"Report write failed: {exc}"))
            return None, None


def build_cleanup_suggestions(
    duplicate_group_uid: str,
    sha256: str,
    content_uid: str,
    master: KbFileInstance,
    instances: list[KbFileInstance],
    vault_path: str | None,
    content_master_file_instance_uid: str | None = None,
) -> list[dict]:
    suggestions: list[dict] = []
    base_reason = "与 master 内容 sha256 相同，建议人工确认是否保留此路径实例"
    if (
        content_master_file_instance_uid
        and content_master_file_instance_uid != master.file_instance_uid
    ):
        base_reason += (
            f"；003 治理 master（{master.file_instance_uid}）"
            f"与 001 登记 master（{content_master_file_instance_uid}）不同，"
            "以本报告 003 master 为准"
        )
    for instance in instances:
        if instance.file_instance_uid == master.file_instance_uid:
            continue
        suggestions.append(
            {
                "duplicate_group_uid": duplicate_group_uid,
                "sha256": sha256,
                "content_uid": content_uid,
                "master_file_instance_uid": master.file_instance_uid,
                "master_source_path": master.source_path,
                "duplicate_file_instance_uid": instance.file_instance_uid,
                "duplicate_source_path": instance.source_path,
                "duplicate_file_name": instance.file_name,
                "suggested_action": SUGGESTED_ACTION_REVIEW_DUPLICATE,
                "auto_execute": False,
                "decision": DECISION_PENDING,
                "reason": base_reason,
                "vault_path": vault_path,
            }
        )
    return suggestions
