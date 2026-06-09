# Repository do OnuModel.

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.inventory.models.onu_model import OnuModel


class OnuModelRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, onu_model_id: UUID) -> OnuModel | None:
        stmt = select(OnuModel).where(OnuModel.onu_model_id == onu_model_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_manufacturer_and_model(
        self, manufacturer_id: UUID, model: str
    ) -> OnuModel | None:
        stmt = select(OnuModel).where(
            OnuModel.manufacturer_id == manufacturer_id,
            OnuModel.model == model,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_manufacturer_and_vendor_id(
        self, manufacturer_id: UUID, vendor_id: str
    ) -> OnuModel | None:
        """Casa uma ONU descoberta com seu modelo via vendor_id GPON.

        Útil mais à frente, na rotina de descoberta de ONUs pendentes
        (Marco da etapa 2 da V1).
        """
        stmt = select(OnuModel).where(
            OnuModel.manufacturer_id == manufacturer_id,
            OnuModel.vendor_id == vendor_id,
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
        category: str | None = None,
        search: str | None = None,
    ) -> tuple[Sequence[OnuModel], int]:
        base_filter = select(OnuModel)
        count_query = select(func.count()).select_from(OnuModel)

        if only_active:
            base_filter = base_filter.where(OnuModel.active.is_(True))
            count_query = count_query.where(OnuModel.active.is_(True))

        if manufacturer_id is not None:
            base_filter = base_filter.where(OnuModel.manufacturer_id == manufacturer_id)
            count_query = count_query.where(OnuModel.manufacturer_id == manufacturer_id)

        if category is not None:
            base_filter = base_filter.where(OnuModel.category == category)
            count_query = count_query.where(OnuModel.category == category)

        if search:
            pattern = f"%{search.lower()}%"
            base_filter = base_filter.where(func.lower(OnuModel.model).like(pattern))
            count_query = count_query.where(func.lower(OnuModel.model).like(pattern))

        page_query = base_filter.order_by(OnuModel.model).offset(offset).limit(limit)

        items_result = await self._session.execute(page_query)
        items: Sequence[OnuModel] = items_result.scalars().all()

        total_result = await self._session.execute(count_query)
        total: int = total_result.scalar_one()

        return items, total

    async def add(self, onu_model: OnuModel) -> None:
        self._session.add(onu_model)
        await self._session.flush()

    async def flush(self) -> None:
        await self._session.flush()
