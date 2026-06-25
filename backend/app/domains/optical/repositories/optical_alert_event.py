# Repository de OpticalAlertEvent

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.inventory.models.chassis import Chassis
from app.domains.inventory.models.olt import Olt
from app.domains.inventory.models.onu import Onu
from app.domains.inventory.models.pon_port import PonPort
from app.domains.inventory.models.slot import Slot
from app.domains.optical.enums import OpticalAlertStatus, OpticalSeverity
from app.domains.optical.models.optical_alert_event import OpticalAlertEvent
from app.domains.optical.models.optical_threshold_policy import (
    OpticalThresholdPolicy,
)


class OpticalAlertEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, alert_id: UUID) -> OpticalAlertEvent | None:
        stmt = select(OpticalAlertEvent).where(OpticalAlertEvent.optical_alert_event_id == alert_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_page(
        self,
        *,
        offset: int,
        limit: int,
        olt_id: UUID | None,
        onu_id: UUID | None,
        status_filter: OpticalAlertStatus | None,
        severity_filter: OpticalSeverity | None,
    ) -> tuple[Sequence[OpticalAlertEvent], int]:
        base = select(OpticalAlertEvent)
        # JOIN com policy somente quando filtrar por severity
        if severity_filter is not None:
            base = base.join(
                OpticalThresholdPolicy,
                OpticalThresholdPolicy.optical_threshold_policy_id == OpticalAlertEvent.policy_id,
            ).where(OpticalThresholdPolicy.severity == severity_filter)

        if onu_id is not None:
            base = base.where(OpticalAlertEvent.onu_id == onu_id)

        # Filtro por olt exige cadeia: onu -> pon_port -> slot -> chassis -> olt.
        if olt_id is not None:
            base = (
                # JOINs adicionados somente se filtro presente.
                base.join(Onu, Onu.onu_id == OpticalAlertEvent.onu_id)
                .join(PonPort, PonPort.pon_port_id == Onu.pon_port_id)
                .join(Slot, Slot.slot_id == PonPort.slot_id)
                .join(Chassis, Chassis.chassis_id == Slot.chassis_id)
                .join(Olt, Olt.olt_id == Chassis.olt_id)
                .where(Olt.olt_id == olt_id)
                .where(Olt.deleted_at.is_(None))
            )

        if status_filter is not None:
            base = base.where(OpticalAlertEvent.status == status_filter)

        items_stmt = (
            base.order_by(OpticalAlertEvent.triggered_at.desc()).offset(offset).limit(limit)
        )
        items_result = await self._session.execute(items_stmt)
        items = items_result.scalars().all()

        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await self._session.execute(count_stmt)).scalar_one()

        return items, int(total)

    async def flush(self) -> None:
        await self._session.flush()
