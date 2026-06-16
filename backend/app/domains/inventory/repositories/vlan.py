# Repository da VLAN.
# Toda leitura cascateia: VLAN "viva" so existe se a OLT pai esta viva
# (olt.deleted_at IS NULL), via JOIN. Pre-check de unicidade também filtra.

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.inventory.models.olt import Olt
from app.domains.inventory.models.vlan import Vlan


class VlanRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, vlan_id: UUID) -> Vlan | None:
        stmt = (
            select(Vlan)
            .join(Olt, Vlan.olt_id == Olt.olt_id)
            .where(Vlan.vlan_id == vlan_id, Olt.deleted_at.is_(None))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_olt_and_number(self, olt_id: UUID, vlan_number: int) -> Vlan | None:
        """Pre-check de unicidade (olt_id, vlan_number) sobre OLT viva."""
        stmt = (
            select(Vlan)
            .join(Olt, Vlan.olt_id == Olt.olt_id)
            .where(
                Vlan.olt_id == olt_id,
                Vlan.vlan_number == vlan_number,
                Olt.deleted_at.is_(None),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_olt(
        self,
        olt_id: UUID,
        *,
        offset: int = 0,
        limit: int = 200,
    ) -> tuple[Sequence[Vlan], int]:
        base = (
            select(Vlan)
            .join(Olt, Vlan.olt_id == Olt.olt_id)
            .where(Vlan.olt_id == olt_id, Olt.deleted_at.is_(None))
        )
        count_stmt = (
            select(func.count())
            .select_from(Vlan)
            .join(Olt, Vlan.olt_id == Olt.olt_id)
            .where(Vlan.olt_id == olt_id, Olt.deleted_at.is_(None))
        )
        items_stmt = base.order_by(Vlan.vlan_number).offset(offset).limit(limit)
        items_result = await self._session.execute(items_stmt)
        items: Sequence[Vlan] = items_result.scalars().all()
        total_result = await self._session.execute(count_stmt)
        total: int = total_result.scalar_one()
        return items, total

    async def add(self, vlan: Vlan) -> None:
        self._session.add(vlan)
        await self._session.flush()
