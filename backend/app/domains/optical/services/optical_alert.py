# Service de OpticalAlertEvent.
# Sem create via API (alertas nascem no worker).

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.pagination import Page, PageParams
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

        # Idempotência: já acknowledged ou resolved não retorna erro;
        # acknowledged volta o mesmo objeto; resolved não admite voltar
        # para acknowledged (transição inválida).
        if alert.status == OpticalAlertStatus.ACKNOWLEDGED:
            return OpticalAlertEventRead.model_validate(alert)
        if alert.status == OpticalAlertStatus.RESOLVED:
            raise OpticalAlertInvalidTransition(
                alert_id,
                current_status=alert.status.value,
                requested_status=OpticalAlertStatus.ACKNOWLEDGED.value,
            )

        alert.status = OpticalAlertStatus.ACKNOWLEDGED
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

        alert.status = OpticalAlertStatus.RESOLVED
        alert.resolved_at = _utcnow()
        await self._session.commit()
        await self._session.refresh(alert)
        log.info(
            "optical_alert.resolved",
            optical_alert_event_id=str(alert_id),
            actor=str(actor),
        )
        return OpticalAlertEventRead.model_validate(alert)
