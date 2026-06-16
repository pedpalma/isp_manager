# Repository do Service Profile.
# Idêntico em forma ao line_profile: cascateamento por OLT viva, pre-check pela tripla (olt_id, name, version).

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.inventory.models.olt import Olt
from app.domains.inventory.models.service_profile import ServiceProfile


class ServiceProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, service_profile_id: UUID) -> ServiceProfile | None:
        stmt = (
            select(ServiceProfile)
            .join(Olt, ServiceProfile.olt_id == Olt.olt_id)
            .where(
                ServiceProfile.service_profile_id == service_profile_id,
                Olt.deleted_at.is_(None),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_olt_name_version(
        self, olt_id: UUID, name: str, version: str
    ) -> ServiceProfile | None:
        stmt = (
            select(ServiceProfile)
            .join(Olt, ServiceProfile.olt_id == Olt.olt_id)
            .where(
                ServiceProfile.olt_id == olt_id,
                ServiceProfile.name == name,
                ServiceProfile.version == version,
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
    ) -> tuple[Sequence[ServiceProfile], int]:
        base = (
            select(ServiceProfile)
            .join(Olt, ServiceProfile.olt_id == Olt.olt_id)
            .where(ServiceProfile.olt_id == olt_id, Olt.deleted_at.is_(None))
        )
        count_stmt = (
            select(func.count())
            .select_from(ServiceProfile)
            .join(Olt, ServiceProfile.olt_id == Olt.olt_id)
            .where(ServiceProfile.olt_id == olt_id, Olt.deleted_at.is_(None))
        )
        items_stmt = (
            base.order_by(ServiceProfile.name, ServiceProfile.version).offset(offset).limit(limit)
        )
        items_result = await self._session.execute(items_stmt)
        items: Sequence[ServiceProfile] = items_result.scalars().all()
        total_result = await self._session.execute(count_stmt)
        total: int = total_result.scalar_one()
        return items, total

    async def add(self, service_profile: ServiceProfile) -> None:
        self._session.add(service_profile)
        await self._session.flush()
