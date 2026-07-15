# Service de OpticalAlertEvent.
# Sem create via API (alertas nascem no worker).

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.pagination import Page, PageParams
from app.domains.audit.enums import AuditAction, AuditResult
from app.domains.audit.services.audit_log import AuditLogService
from app.domains.optical.enums import OpticalAlertStatus, OpticalSeverity
from app.domains.optical.exceptions import (
    OpticalAlertEventNotFound,
    OpticalAlertInvalidTransition,
)
from app.domains.optical.repositories.optical_alert_event import (
    OpticalAlertEventRepository,
)
from app.domains.optical.schemas.optical_alert_event import OpticalAlertEventRead

log = structlog.get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)  # noqa: UP017


class OpticalAlertService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = OpticalAlertEventRepository(session)
        self._audit = AuditLogService(session)

    async def get(self, alert_id: UUID, *, actor: Actor) -> OpticalAlertEventRead:
        del actor
        alert = await self._repo.get_by_id(alert_id)
        if alert is None:
            raise OpticalAlertEventNotFound(alert_id)
        return OpticalAlertEventRead.model_validate(alert)

    async def list_page(
        self,
        *,
        params: PageParams,
        olt_id: UUID | None,
        onu_id: UUID | None,
        status_filter: OpticalAlertStatus | None,
        severity_filter: OpticalSeverity | None,
        actor: Actor,
    ) -> Page[OpticalAlertEventRead]:
        del actor
        items, total = await self._repo.list_page(
            offset=params.offset,
            limit=params.limit,
            olt_id=olt_id,
            onu_id=onu_id,
            status_filter=status_filter,
            severity_filter=severity_filter,
        )
        return Page[OpticalAlertEventRead](
            items=[OpticalAlertEventRead.model_validate(a) for a in items],
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    async def acknowledge(self, alert_id: UUID, *, actor: Actor) -> OpticalAlertEventRead:
        alert = await self._repo.get_by_id(alert_id)
        if alert is None:
            raise OpticalAlertEventNotFound(alert_id)

        if alert.status == OpticalAlertStatus.ACKNOWLEDGED:
            return OpticalAlertEventRead.model_validate(alert)
        if alert.status == OpticalAlertStatus.RESOLVED:
            raise OpticalAlertInvalidTransition(
                alert_id,
                current_status=alert.status.value,
                requested_status=OpticalAlertStatus.ACKNOWLEDGED.value,
            )

        prior_status = alert.status.value
        alert_onu_id = alert.onu_id

        alert.status = OpticalAlertStatus.ACKNOWLEDGED
        await self._session.flush()

        await self._audit.record(
            actor=actor,
            action=AuditAction.OPTICAL_ALERT_ACKNOWLEDGED,
            result=AuditResult.SUCCESS,
            entity_type="optical_alert_event",
            entity_id=alert_id,
            onu_id=alert_onu_id,
            before={"status": prior_status},
            after={"status": OpticalAlertStatus.ACKNOWLEDGED.value},
        )

        await self._session.commit()
        await self._session.refresh(alert)
        log.info(
            "optical_alert.acknowledged",
            optical_alert_event_id=str(alert_id),
            actor=str(actor),
        )
        return OpticalAlertEventRead.model_validate(alert)

    async def resolve(self, alert_id: UUID, *, actor: Actor) -> OpticalAlertEventRead:
        alert = await self._repo.get_by_id(alert_id)
        if alert is None:
            raise OpticalAlertEventNotFound(alert_id)

        # Idempotência: já resolved retorna o mesmo objeto.
        if alert.status == OpticalAlertStatus.RESOLVED:
            return OpticalAlertEventRead.model_validate(alert)

        prior_status = alert.status.value
        alert_onu_id = alert.onu_id
        resolved_at = _utcnow()

        alert.status = OpticalAlertStatus.RESOLVED
        alert.resolved_at = resolved_at
        await self._session.flush()

        await self._audit.record(
            actor=actor,
            action=AuditAction.OPTICAL_ALERT_RESOLVED,
            result=AuditResult.SUCCESS,
            entity_type="optical_alert_event",
            entity_id=alert_id,
            onu_id=alert_onu_id,
            before={"status": prior_status, "resolved_at": None},
            after={
                "status": OpticalAlertStatus.RESOLVED.value,
                "resolved_at": resolved_at.isoformat(),
            },
        )

        await self._session.commit()
        await self._session.refresh(alert)
        log.info(
            "optical_alert.resolved",
            optical_alert_event_id=str(alert_id),
            actor=str(actor),
        )
        return OpticalAlertEventRead.model_validate(alert)
