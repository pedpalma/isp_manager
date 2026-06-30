# Repository de NormalizedCommand

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.provisioning.models.normalized_command import NormalizedCommand


class NormalizedCommandRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, normalized_command_id: UUID) -> NormalizedCommand | None:
        stmt = select(NormalizedCommand).where(
            NormalizedCommand.normalized_command_id == normalized_command_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_by_key(
        self,
        *,
        manufacturer_id: UUID,
        olt_model_id: UUID | None,
        command_key: str,
        version_constraint: str | None,
    ) -> NormalizedCommand | None:
        """Pré-Check de unicidade PARCIAL"""
        stmt = select(NormalizedCommand).where(
            NormalizedCommand.manufacturer_id == manufacturer_id,
            NormalizedCommand.command_key == command_key,
            NormalizedCommand.active.is_(True),
        )
        if olt_model_id is None:
            stmt = stmt.where(NormalizedCommand.olt_model_id.is_(None))
        else:
            stmt = stmt.where(NormalizedCommand.olt_model_id == olt_model_id)
        if version_constraint is None:
            stmt = stmt.where(NormalizedCommand.version_constraint.is_(None))
        else:
            stmt = stmt.where(NormalizedCommand.version_constraint == version_constraint)

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_page(
        self,
        *,
        offset: int,
        limit: int,
        manufacturer_id: UUID | None = None,
        olt_model_id: UUID | None = None,
        command_key: str | None = None,
        command_type: str | None = None,
        active: bool | None = None,
    ) -> tuple[Sequence[NormalizedCommand], int]:
        """Listagem paginada com filtros opcionais."""
        base = select(NormalizedCommand)
        count_query = select(func.count()).select_from(NormalizedCommand)

        if manufacturer_id is not None:
            base = base.where(NormalizedCommand.manufacturer_id == manufacturer_id)
            count_query = count_query.where(
                NormalizedCommand.manufacturer_id == manufacturer_id,
            )
        if olt_model_id is not None:
            base = base.where(NormalizedCommand.olt_model_id == olt_model_id)
            count_query = count_query.where(
                NormalizedCommand.olt_model_id == olt_model_id,
            )
        if command_key is not None:
            base = base.where(NormalizedCommand.command_key == command_key)
            count_query = count_query.where(
                NormalizedCommand.command_key == command_key,
            )
        if active is not None:
            base = base.where(NormalizedCommand.active.is_(active))
            count_query = count_query.where(NormalizedCommand.active.is_(active))

        page_query = (
            base.order_by(
                NormalizedCommand.command_key.asc(),
                NormalizedCommand.version_constraint.asc().nullsfirst(),
            )
            .offset(offset)
            .limit(limit)
        )
        items_result = await self._session.execute(page_query)
        items: Sequence[NormalizedCommand] = items_result.scalars().all()

        total_result = await self._session.execute(count_query)
        total: int = total_result.scalar_one()

        return items, total

    async def add(self, obj: NormalizedCommand) -> None:
        self._session.add(obj)
        await self._session.flush()

    async def flush(self) -> None:
        await self._session.flush()
