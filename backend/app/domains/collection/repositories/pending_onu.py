# Repository do PendingOnu.

# Esta camada é somente leitura no contexto da API: o worker
# escreve via session sync usando upsert.
# A unicidade (olt_id, pon_port_id, serial) é a âncora.
#
# Listagem filtra por OLT viva via JOIN (mesmo padrão dos olt_children).
# Ordem default: last_seen_at DESC, alinhada com idx_pending_onu_unresolved.

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.collection.enums import PendingOnuState
from app.domains.collection.models.pending_onu import PendingOnu
from app.domains.inventory.models.olt import Olt


class PendingOnuRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, pending_onu_id: UUID) -> PendingOnu | None:
        stmt = (
            select(PendingOnu)
            .join(Olt, Olt.olt_id == PendingOnu.olt_id)
            .where(
                PendingOnu.pending_onu_id == pending_onu_id,
                Olt.deleted_at.is_(None),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_page(
        self,
        *,
        limit: int,
        offset: int,
        olt_id: UUID | None,
        pon_port_id: UUID | None,
        state: PendingOnuState | None,
    ) -> tuple[Sequence[PendingOnu], int]:
        base = (
            select(PendingOnu)
            .join(Olt, Olt.olt_id == PendingOnu.olt_id)
            .where(Olt.deleted_at.is_(None))
        )
        if olt_id is not None:
            base = base.where(PendingOnu.olt_id == olt_id)
        if pon_port_id is not None:
            base = base.where(PendingOnu.pon_port_id == pon_port_id)
        if state is not None:
            base = base.where(PendingOnu.state == state)

        items_stmt = base.order_by(PendingOnu.last_seen_at.desc()).offset(offset).limit(limit)
        items_result = await self._session.execute(items_stmt)
        items = items_result.scalars().all()

        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await self._session.execute(count_stmt)).scalar_one()

        return items, int(total)
