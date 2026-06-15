from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from app.core.config import AppConfig, ensure_readonly
from app.core.database import create_db_engine, create_session_factory
from app.core.parser_routing import (
    DECISION_ROUTE,
    DECISION_UNKNOWN,
    DECISION_UNSUPPORTED,
    ROUTING_RULES_VERSION,
    RouteType,
    ext_from_path,
    match_route_type,
    normalize_file_ext,
)
from app.core.vault_paths import VAULT_COPIED
from app.models.file import KbFileContent, KbFileInstance
from app.models.vault import KbRawVaultObject

logger = logging.getLogger(__name__)

STATUS_CONTENT_REGISTERED = "CONTENT_REGISTERED"
STATUS_DISCOVERED = "DISCOVERED"


@dataclass
class RouteError:
    sha256: str
    message: str


@dataclass
class ParserRouteDecision:
    content_uid: str
    sha256: str
    file_ext: str | None
    mime_type: str | None
    vault_path: str | None
    route_type: RouteType
    decision: str
    rule_name: str | None
    reason: str
    future_parser_hint: str
    parse_status: str | None
    vault_uid: str | None = None

    def to_dict(self) -> dict:
        return {
            "content_uid": self.content_uid,
            "sha256": self.sha256,
            "vault_path": self.vault_path,
            "file_ext": self.file_ext,
            "mime_type": self.mime_type,
            "route_type": self.route_type.value,
            "decision": self.decision,
            "rule_name": self.rule_name,
            "reason": self.reason,
            "future_parser_hint": self.future_parser_hint,
            "parse_status": self.parse_status,
            "vault_uid": self.vault_uid,
        }


@dataclass
class ParserRouteResult:
    candidates: int = 0
    routed: int = 0
    skipped: int = 0
    unknown: int = 0
    unsupported: int = 0
    errors: list[RouteError] = field(default_factory=list)
    decisions: list[ParserRouteDecision] = field(default_factory=list)
    report_path: Path | None = None

    def to_dict(self) -> dict:
        return {
            "candidates": self.candidates,
            "routed": self.routed,
            "skipped": self.skipped,
            "unknown": self.unknown,
            "unsupported": self.unsupported,
            "errors": [
                {"sha256": item.sha256, "message": item.message} for item in self.errors
            ],
            "report_path": self.report_path.as_posix() if self.report_path else None,
        }


class ParserRouterService:
    def __init__(self, config: AppConfig) -> None:
        ensure_readonly(config)
        self.config = config
        engine = create_db_engine(config)
        self.session_factory = create_session_factory(engine)

    def route_parsers(
        self,
        limit: int | None = None,
        sha256: str | None = None,
        content_uid: str | None = None,
    ) -> ParserRouteResult:
        result = ParserRouteResult()
        contents = self._load_candidates(
            sha256=sha256,
            content_uid=content_uid,
            limit=limit,
        )
        result.candidates = len(contents)

        for content in contents:
            try:
                decision = self._route_content(content)
                result.decisions.append(decision)
                if decision.decision == DECISION_ROUTE:
                    result.routed += 1
                elif decision.decision == DECISION_UNKNOWN:
                    result.unknown += 1
                elif decision.decision == DECISION_UNSUPPORTED:
                    result.unsupported += 1
            except Exception as exc:
                logger.exception("Parser routing failed for sha256=%s", content.sha256)
                result.errors.append(
                    RouteError(sha256=content.sha256 or "", message=str(exc))
                )

        result.report_path = self._write_report(result)
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
                KbFileContent.status == STATUS_CONTENT_REGISTERED,
                KbFileContent.vault_status == VAULT_COPIED,
            )
            if target_sha:
                query = query.where(KbFileContent.sha256 == target_sha)
            query = query.order_by(KbFileContent.id.asc())
            if limit is not None:
                query = query.limit(limit)
            return list(session.scalars(query).all())

    def _route_content(self, content: KbFileContent) -> ParserRouteDecision:
        sha256 = content.sha256
        assert sha256 is not None

        with self.session_factory() as session:
            db_content = session.scalar(
                select(KbFileContent).where(KbFileContent.sha256 == sha256)
            )
            if db_content is None:
                raise RuntimeError(f"Content not found for sha256={sha256}")

            vault_object = session.scalar(
                select(KbRawVaultObject).where(KbRawVaultObject.sha256 == sha256)
            )
            vault_path = db_content.vault_path
            vault_uid: str | None = None
            if vault_object is not None:
                if not vault_path:
                    vault_path = vault_object.vault_path
                vault_uid = vault_object.vault_uid
            elif not vault_path:
                logger.warning("vault_path missing for sha256=%s", sha256)

            fallback_ext = self._resolve_fallback_ext(session, db_content)
            normalized_ext = normalize_file_ext(db_content.file_ext)

            route_type, decision, rule_name, future_parser_hint, reason = match_route_type(
                file_ext=normalized_ext,
                mime_type=db_content.mime_type,
                fallback_ext=fallback_ext,
            )

            if vault_path is None:
                reason = f"{reason}; vault_path is null in database metadata"

            logger.info(
                "Parser route processed sha256=%s route_type=%s decision=%s rule=%s",
                sha256,
                route_type.value,
                decision,
                rule_name,
            )

            return ParserRouteDecision(
                content_uid=db_content.content_uid,
                sha256=sha256,
                file_ext=normalized_ext or fallback_ext,
                mime_type=db_content.mime_type,
                vault_path=vault_path,
                route_type=route_type,
                decision=decision,
                rule_name=rule_name,
                reason=reason,
                future_parser_hint=future_parser_hint,
                parse_status=db_content.parse_status,
                vault_uid=vault_uid,
            )

    def _resolve_fallback_ext(
        self,
        session,
        content: KbFileContent,
    ) -> str | None:
        if normalize_file_ext(content.file_ext):
            return None

        instances_query = (
            select(KbFileInstance)
            .where(
                KbFileInstance.sha256 == content.sha256,
                KbFileInstance.status == STATUS_DISCOVERED,
            )
            .order_by(KbFileInstance.created_at.asc(), KbFileInstance.id.asc())
        )
        instances = list(session.scalars(instances_query).all())
        if not instances:
            return None

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
            ext = ext_from_path(instance.file_name)
            if ext:
                return ext
            ext = ext_from_path(instance.source_path)
            if ext:
                return ext
        return None

    def _write_report(self, result: ParserRouteResult) -> Path | None:
        reports_root = self.config.storage.reports_root
        reports_root.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        generated_at = datetime.now(UTC).replace(tzinfo=UTC).isoformat().replace("+00:00", "Z")
        report_path = reports_root / f"parser_route_report_{timestamp}.json"

        payload = {
            "report_type": "parser_route_report",
            "pipeline_version": self.config.pipeline_version,
            "routing_rules_version": ROUTING_RULES_VERSION,
            "generated_at": generated_at,
            "summary": {
                "candidates": result.candidates,
                "routed": result.routed,
                "skipped": result.skipped,
                "unknown": result.unknown,
                "unsupported": result.unsupported,
                "errors": len(result.errors),
            },
            "decisions": [item.to_dict() for item in result.decisions],
            "errors": [
                {"sha256": item.sha256, "message": item.message} for item in result.errors
            ],
        }

        try:
            report_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            logger.info("Wrote parser route report: %s", report_path)
            return report_path
        except Exception as exc:
            logger.exception("Failed to write parser route report")
            result.errors.append(RouteError(sha256="", message=f"Report write failed: {exc}"))
            return None
