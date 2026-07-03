# Repository de ProvisioningStep (M18d).

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.provisioning.models.provisioning_step import ProvisioningStep


class ProvisioningStepRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_order(self, provisioning_order_id: UUID) -> Sequence[ProvisioningStep]:
        """Lista steps da ordem em ordem crescente de step_order.

        Cobre os índices idx_provisioning_step_order + uq_provisioning_step_order."""
        stmt = (
            select(ProvisioningStep)
            .where(ProvisioningStep.provisioning_order_id == provisioning_order_id)
            .order_by(ProvisioningStep.step_order.asc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
