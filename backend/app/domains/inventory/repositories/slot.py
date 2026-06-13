# Repository do Slot. Cascateia: slot "vivo" exige OLT pai viva (via chassis).

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.inventory.models.chassis import Chassis
from app.domains.inventory.models.olt import Olt
from app.domains.inventory.models.slot import Slot


class SlotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, slot_id: UUID) -> Slot | None:
        stmt = (
            select(Slot)
            .join(Chassis, Slot.chassis_id == Chassis.chassis_id)
            .join(Olt, Chassis.olt_id == Olt.olt_id)
            .where(
                Slot.slot_id == slot_id,
                Olt.deleted_at.is_(None),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_chassis_and_index(
        self,
        chassis_id: UUID,
        slot_index: int,
    ) -> Slot | None:
        stmt = (
            select(Slot)
            .join(Chassis, Slot.chassis_id == Chassis.chassis_id)
            .join(Olt, Chassis.olt_id == Olt.olt_id)
            .where(
                Slot.chassis_id == chassis_id,
                Slot.slot_index == slot_index,
                Olt.deleted_at.is_(None),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_chassis(
        self,
        chassis_id: UUID,
        *,
        offset: int = 0,
        limit: int = 200,
    ) -> tuple[Sequence[Slot], int]:
        base = (
            select(Slot)
            .join(Chassis, Slot.chassis_id == Chassis.chassis_id)
            .join(Olt, Chassis.olt_id == Olt.olt_id)
            .where(
                Slot.chassis_id == chassis_id,
                Olt.deleted_at.is_(None),
            )
        )
        count_stmt = (
            select(func.count())
            .select_from(Slot)
            .join(Chassis, Slot.chassis_id == Chassis.chassis_id)
            .join(Olt, Chassis.olt_id == Olt.olt_id)
            .where(
                Slot.chassis_id == chassis_id,
                Olt.deleted_at.is_(None),
            )
        )

        items_stmt = base.order_by(Slot.slot_index).offset(offset).limit(limit)
        items_result = await self._session.execute(items_stmt)
        items: Sequence[Slot] = items_result.scalars().all()

        total_result = await self._session.execute(count_stmt)
        total: int = total_result.scalar_one()

        return items, total

    async def list_all_for_chassis_ids(
        self,
        chassis_ids: Sequence[UUID],
    ) -> Sequence[Slot]:
        """Sem paginação. Usado pela árvore de topologia.
        Filtragem por OLT viva é redundante aqui (chassis_ids já vem filtrado pelo
        ChassisRepository), mas mantida por defesa em profundidade."""
        if not chassis_ids:
            return []
        stmt = (
            select(Slot)
            .join(Chassis, Slot.chassis_id == Chassis.chassis_id)
            .join(Olt, Chassis.olt_id == Olt.olt_id)
            .where(
                Slot.chassis_id.in_(chassis_ids),
                Olt.deleted_at.is_(None),
            )
            .order_by(Slot.chassis_id, Slot.slot_index)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def add(self, slot: Slot) -> None:
        self._session.add(slot)
        await self._session.flush()
