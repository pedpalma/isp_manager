# Service do domínio de auditoria.

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.actor import Actor
from app.core.logging import get_logger, get_request_id
from app.core.pagination import Page, PageParams
from app.domains.audit.enums import AuditAction, AuditResult
from app.domains.audit.exceptions import AuditLogNotFound
from app.domains.audit.masking import scrub_secrets
from app.domains.audit.models.audit_log import AuditLog
from app.domains.audit.repositories.audit_log import AuditLogRepository
from app.domains.audit.schemas.audit_log import AuditLogRead

log = get_logger(__name__)


def _build_entry(
    *,
    actor: Actor,
    action: AuditAction,
    result: AuditResult,
    entity_type: str,
    entity_id: UUID,
    olt_id: UUID | None,
    onu_id: UUID | None,
    provisioning_order_id: UUID | None,
    error_detail: str | None,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    extra: dict[str, Any] | None,
) -> AuditLog:
    """Monta um AuditLog aplicando mascaramento de secrets."""
    app_user_id = None if actor.is_system else actor.actor_id

    base_extra: dict[str, Any] = {
        "actor_username": actor.username,
        "actor_is_system": actor.is_system,
    }
    if extra:
        base_extra.update(extra)

    return AuditLog(
        app_user_id=app_user_id,
        olt_id=olt_id,
        onu_id=onu_id,
        provisioning_order_id=provisioning_order_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action.value,
        result=result.value,
        error_detail=error_detail,
        before_data=scrub_secrets(before),
        after_data=scrub_secrets(after),
        event_metadata=scrub_secrets(base_extra),
        request_id=get_request_id(),
    )


class AuditLogService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = AuditLogRepository(session)

    async def get(self, audit_log_id: UUID, *, actor: Actor) -> AuditLogRead:
        del actor
        entry = await self._repo.get_by_id(audit_log_id)
        if entry is None:
            raise AuditLogNotFound(audit_log_id)
        return AuditLogRead.model_validate(entry)

    async def list_page(
        self,
        *,
        params: PageParams,
        actor: Actor,
        app_user_id: UUID | None = None,
        olt_id: UUID | None = None,
        onu_id: UUID | None = None,
        provisioning_order_id: UUID | None = None,
        entity_type: str | None = None,
        entity_id: UUID | None = None,
        action: str | None = None,
        result: str | None = None,
        request_id: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> Page[AuditLogRead]:
        del actor
        items, total = await self._repo.list_page(
            app_user_id=app_user_id,
            olt_id=olt_id,
            onu_id=onu_id,
            provisioning_order_id=provisioning_order_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            result=result,
            request_id=request_id,
            created_from=created_from,
            created_to=created_to,
            offset=params.offset,
            limit=params.limit,
        )
        return Page[AuditLogRead](
            items=[AuditLogRead.model_validate(i) for i in items],
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    async def record(
        self,
        *,
        actor: Actor,
        action: AuditAction,
        result: AuditResult,
        entity_type: str,
        entity_id: UUID,
        olt_id: UUID | None = None,
        onu_id: UUID | None = None,
        provisioning_order_id: UUID | None = None,
        error_detail: str | None = None,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Grava um evento de auditoria na sessão async da API."""
        entry = _build_entry(
            actor=actor,
            action=action,
            result=result,
            entity_type=entity_type,
            entity_id=entity_id,
            olt_id=olt_id,
            onu_id=onu_id,
            provisioning_order_id=provisioning_order_id,
            error_detail=error_detail,
            before=before,
            after=after,
            extra=extra,
        )
        self._repo.add(entry)
        await self._repo.flush()
        log.info(
            "audit_log.recorded",
            action=entry.action,
            result=entry.result,
            entity_type=entry.entity_type,
            entity_id=str(entry.entity_id),
            app_user_id=str(entry.app_user_id) if entry.app_user_id else None,
        )
        return entry


def record_sync(
    session: Session,
    *,
    actor: Actor,
    action: AuditAction,
    result: AuditResult,
    entity_type: str,
    entity_id: UUID,
    olt_id: UUID | None = None,
    onu_id: UUID | None = None,
    provisioning_order_id: UUID | None = None,
    error_detail: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> AuditLog:
    """Espelho síncrono de `AuditLogService.record`."""
    entry = _build_entry(
        actor=actor,
        action=action,
        result=result,
        entity_type=entity_type,
        entity_id=entity_id,
        olt_id=olt_id,
        onu_id=onu_id,
        provisioning_order_id=provisioning_order_id,
        error_detail=error_detail,
        before=before,
        after=after,
        extra=extra,
    )
    session.add(entry)
    session.flush()
    log.info(
        "audit_log.recorded",
        action=entry.action,
        result=entry.result,
        entity_type=entry.entity_type,
        entity_id=str(entry.entity_id),
        app_user_id=str(entry.app_user_id) if entry.app_user_id else None,
    )
    return entry


def _order_by_created_at_desc(entries: Sequence[AuditLog]) -> Sequence[AuditLog]:
    return sorted(entries, key=lambda e: e.created_at, reverse=True)
