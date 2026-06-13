# Repository da PonPort. Cascateia até OLT viva (via slot e chassis).

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.inventory.models.chassis import Chassis
from app.domains.inventory.models.olt import Olt
from app.domains.inventory.models.pon_port import PonPort
from app.domains.inventory.models.slot import Slot


class PonPortRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, pon_port_id: UUID) -> PonPort | None:
        stmt = (
            select(PonPort)
            .join(Slot, PonPort.slot_id == Slot.slot_id)
            .join(Chassis, Slot.chassis_id == Chassis.chassis_id)
            .join(Olt, Chassis.olt_id == Olt.olt_id)
            .where(
                PonPort.pon_port_id == pon_port_id,
                Olt.deleted_at.is_(None),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_slot_and_index(
        self,
        slot_id: UUID,
        pon_index: int,
    ) -> PonPort | None:
        stmt = (
            select(PonPort)
            .join(Slot, PonPort.slot_id == Slot.slot_id)
            .join(Chassis, Slot.chassis_id == Chassis.chassis_id)
            .join(Olt, Chassis.olt_id == Olt.olt_id)
            .where(
                PonPort.slot_id == slot_id,
                PonPort.pon_index == pon_index,
                Olt.deleted_at.is_(None),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_slot(
        self,
        slot_id: UUID,
        *,
        offset: int = 0,
        limit: int = 200,
    ) -> tuple[Sequence[PonPort], int]:
        base = (
            select(PonPort)
            .join(Slot, PonPort.slot_id == Slot.slot_id)
            .join(Chassis, Slot.chassis_id == Chassis.chassis_id)
            .join(Olt, Chassis.olt_id == Olt.olt_id)
            .where(
                PonPort.slot_id == slot_id,
                Olt.deleted_at.is_(None),
            )
        )
        count_stmt = (
            select(func.count())
            .select_from(PonPort)
            .join(Slot, PonPort.slot_id == Slot.slot_id)
            .join(Chassis, Slot.chassis_id == Chassis.chassis_id)
            .join(Olt, Chassis.olt_id == Olt.olt_id)
            .where(
                PonPort.slot_id == slot_id,
                Olt.deleted_at.is_(None),
            )
        )

        items_stmt = base.order_by(PonPort.pon_index).offset(offset).limit(limit)
        items_result = await self._session.execute(items_stmt)
        items: Sequence[PonPort] = items_result.scalars().all()

        total_result = await self._session.execute(count_stmt)
        total: int = total_result.scalar_one()

        return items, total

    async def list_all_for_slot_ids(
        self,
        slot_ids: Sequence[UUID],
    ) -> Sequence[PonPort]:
        if not slot_ids:
            return []
        stmt = (
            select(PonPort)
            .join(Slot, PonPort.slot_id == Slot.slot_id)
            .join(Chassis, Slot.chassis_id == Chassis.chassis_id)
            .join(Olt, Chassis.olt_id == Olt.olt_id)
            .where(
                PonPort.slot_id.in_(slot_ids),
                Olt.deleted_at.is_(None),
            )
            .order_by(PonPort.slot_id, PonPort.pon_index)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def add(self, pon_port: PonPort) -> None:
        self._session.add(pon_port)
        await self._session.flush()
