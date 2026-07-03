# Repository de ProvisioningRollback (M18d).


from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.provisioning.models.provisioning_rollback import ProvisioningRollback


class ProvisioningRollbackRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_order(self, provisioning_order_id: UUID) -> ProvisioningRollback | None:
        """Recupera o rollback (0 ou 1) associado à ordem.
        V1 usa order_by created_at DESC + limit(1) como safety
        net caso algum caminho no futuro grave duplicado."""
        stmt = (
            select(ProvisioningRollback)
            .where(ProvisioningRollback.provisioning_order_id == provisioning_order_id)
            .order_by(ProvisioningRollback.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
