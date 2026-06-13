# Repository do Chassis.

# Toda leitura cascateia: chassis "vivo" só existe se a OLT pai está viva (deleted_at IS NULL).
# Implementado via JOIN com a tabela olt.

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.inventory.models.chassis import Chassis
from app.domains.inventory.models.olt import Olt


class ChassisRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, chassis_id: UUID) -> Chassis | None:
        """Retorna chassis só se a OLT pai estiver viva."""
        stmt = (
            select(Chassis)
            .join(Olt, Chassis.olt_id == Olt.olt_id)
            .where(
                Chassis.chassis_id == chassis_id,
                Olt.deleted_at.is_(None),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_olt_and_index(
        self,
        olt_id: UUID,
        chassis_index: int,
    ) -> Chassis | None:
        """Pré-check de unicidade (olt_id, chassis_index). Filtra OLT viva."""
        stmt = (
            select(Chassis)
            .join(Olt, Chassis.olt_id == Olt.olt_id)
            .where(
                Chassis.olt_id == olt_id,
                Chassis.chassis_index == chassis_index,
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
    ) -> tuple[Sequence[Chassis], int]:
        """Lista paginada de chassis de uma OLT. Total geral por OLT viva."""
        base = (
            select(Chassis)
            .join(Olt, Chassis.olt_id == Olt.olt_id)
            .where(
                Chassis.olt_id == olt_id,
                Olt.deleted_at.is_(None),
            )
        )
        count_stmt = (
            select(func.count())
            .select_from(Chassis)
            .join(Olt, Chassis.olt_id == Olt.olt_id)
            .where(
                Chassis.olt_id == olt_id,
                Olt.deleted_at.is_(None),
            )
        )

        items_stmt = base.order_by(Chassis.chassis_index).offset(offset).limit(limit)
        items_result = await self._session.execute(items_stmt)
        items: Sequence[Chassis] = items_result.scalars().all()

        total_result = await self._session.execute(count_stmt)
        total: int = total_result.scalar_one()

        return items, total

    async def list_all_for_olt(self, olt_id: UUID) -> Sequence[Chassis]:
        """Sem paginação. Usado pela árvore de topologia."""
        stmt = (
            select(Chassis)
            .join(Olt, Chassis.olt_id == Olt.olt_id)
            .where(
                Chassis.olt_id == olt_id,
                Olt.deleted_at.is_(None),
            )
            .order_by(Chassis.chassis_index)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def add(self, chassis: Chassis) -> None:
        self._session.add(chassis)
        await self._session.flush()
