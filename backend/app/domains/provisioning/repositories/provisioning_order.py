# Repository de ProvisioningOrder

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.inventory.models.olt import Olt
from app.domains.provisioning.enums import (
    ACTIVE_PROVISIONING_STATUSES,
    ProvisioningStatus,
)
from app.domains.provisioning.models.provisioning_order import ProvisioningOrder


class ProvisioningOrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, provisioning_order_id: UUID) -> ProvisioningOrder | None:
        stmt = (
            select(ProvisioningOrder)
            .join(Olt, Olt.olt_id == ProvisioningOrder.olt_id)
            .where(
                ProvisioningOrder.provisioning_order_id == provisioning_order_id,
                Olt.deleted_at.is_(None),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_idempotency_key(self, idempotency_key: str) -> ProvisioningOrder | None:
        """Pré-check 409 antes de bater o índice único"""
        stmt = select(ProvisioningOrder).where(
            ProvisioningOrder.idempotency_key == idempotency_key,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def has_active_for_onu(self, onu_id: UUID) -> bool:
        """Confere se já existe uma ordem ativa para a ONU especificada."""
        stmt = (
            select(func.count())
            .select_from(ProvisioningOrder)
            .where(
                ProvisioningOrder.onu_id == onu_id,
                ProvisioningOrder.status.in_(list(ACTIVE_PROVISIONING_STATUSES)),
            )
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one()) > 0

    async def list_page(
        self,
        *,
        limit: int,
        offset: int,
        olt_id: UUID | None,
        status_filter: ProvisioningStatus | None,
        app_user_id: UUID | None,
        created_from: datetime | None,
        created_to: datetime | None,
    ) -> tuple[Sequence[ProvisioningOrder], int]:
        base = (
            select(ProvisioningOrder)
            .join(Olt, Olt.olt_id == ProvisioningOrder.olt_id)
            .where(Olt.deleted_at.is_(None))
        )
        if olt_id is not None:
            base = base.where(ProvisioningOrder.olt_id == olt_id)
        if status_filter is not None:
            base = base.where(ProvisioningOrder.status == status_filter)
        if app_user_id is not None:
            base = base.where(ProvisioningOrder.app_user_id == app_user_id)
        if created_from is not None:
            base = base.where(ProvisioningOrder.created_at >= created_from)
        if created_to is not None:
            base = base.where(ProvisioningOrder.created_at <= created_to)

        # Ordem alinhada com o idx_provisioning_order_olt_status
        items_stmt = base.order_by(ProvisioningOrder.created_at.desc()).offset(offset).limit(limit)

        items_result = await self._session.execute(items_stmt)
        items = items_result.scalars().all()

        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await self._session.execute(count_stmt)).scalar_one()

        return items, int(total)

    async def add(self, order: ProvisioningOrder) -> None:
        self._session.add(order)
        await self._session.flush()
