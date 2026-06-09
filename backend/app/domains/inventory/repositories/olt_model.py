# Repository do OltModel.

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.inventory.models.olt_model import OltModel


class OltModelRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, olt_model_id: UUID) -> OltModel | None:
        stmt = select(OltModel).where(OltModel.olt_model_id == olt_model_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_manufacturer_and_model(
        self, manufacturer_id: UUID, model: str
    ) -> OltModel | None:
        stmt = select(OltModel).where(
            OltModel.manufacturer_id == manufacturer_id,
            OltModel.model == model,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_page(
        self,
        *,
        offset: int,
        limit: int,
        only_active: bool = False,
        manufacturer_id: UUID | None = None,
        search: str | None = None,
    ) -> tuple[Sequence[OltModel], int]:
        base_filter = select(OltModel)
        count_query = select(func.count()).select_from(OltModel)

        if only_active:
            base_filter = base_filter.where(OltModel.active.is_(True))
            count_query = count_query.where(OltModel.active.is_(True))

        if manufacturer_id is not None:
            base_filter = base_filter.where(OltModel.manufacturer_id == manufacturer_id)
            count_query = count_query.where(OltModel.manufacturer_id == manufacturer_id)

        if search:
            pattern = f"%{search.lower()}%"
            base_filter = base_filter.where(func.lower(OltModel.model).like(pattern))
            count_query = count_query.where(func.lower(OltModel.model).like(pattern))

        page_query = base_filter.order_by(OltModel.model).offset(offset).limit(limit)

        items_result = await self._session.execute(page_query)
        items: Sequence[OltModel] = items_result.scalars().all()

        total_result = await self._session.execute(count_query)
        total: int = total_result.scalar_one()

        return items, total

    async def add(self, olt_model: OltModel) -> None:
        self._session.add(olt_model)
        await self._session.flush()

    async def flush(self) -> None:
        await self._session.flush()
