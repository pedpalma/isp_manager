# Repository do Line Profile.
# Mesma logica de cascateamento por OLT viva via JOIN. Pre-check pela tripla (olt_id, name, version).

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.inventory.models.line_profile import LineProfile
from app.domains.inventory.models.olt import Olt


class LineProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, line_profile_id: UUID) -> LineProfile | None:
        stmt = (
            select(LineProfile)
            .join(Olt, LineProfile.olt_id == Olt.olt_id)
            .where(
                LineProfile.line_profile_id == line_profile_id,
                Olt.deleted_at.is_(None),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_olt_name_version(
        self, olt_id: UUID, name: str, version: str
    ) -> LineProfile | None:
        """Pre-check de unicidade (olt_id, name, version) sobre OLT viva."""
        stmt = (
            select(LineProfile)
            .join(Olt, LineProfile.olt_id == Olt.olt_id)
            .where(
                LineProfile.olt_id == olt_id,
                LineProfile.name == name,
                LineProfile.version == version,
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
    ) -> tuple[Sequence[LineProfile], int]:
        base = (
            select(LineProfile)
            .join(Olt, LineProfile.olt_id == Olt.olt_id)
            .where(LineProfile.olt_id == olt_id, Olt.deleted_at.is_(None))
        )
        count_stmt = (
            select(func.count())
            .select_from(LineProfile)
            .join(Olt, LineProfile.olt_id == Olt.olt_id)
            .where(LineProfile.olt_id == olt_id, Olt.deleted_at.is_(None))
        )
        items_stmt = (
            base.order_by(LineProfile.name, LineProfile.version)
            .offset(offset)
            .limit(limit)
        )
        items_result = await self._session.execute(items_stmt)
        items: Sequence[LineProfile] = items_result.scalars().all()
        total_result = await self._session.execute(count_stmt)
        total: int = total_result.scalar_one()
        return items, total

    async def add(self, line_profile: LineProfile) -> None:
        self._session.add(line_profile)
        await self._session.flush()
