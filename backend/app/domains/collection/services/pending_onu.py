# Service de PendingOnu.

# Escrita acontece via worker (discovery_worker.py).
# A API expõe apenas listagem paginada e o detalhe.

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.pagination import Page, PageParams
from app.domains.collection.enums import PendingOnuState
from app.domains.collection.exceptions import PendingOnuNotFound
from app.domains.collection.repositories.pending_onu import PendingOnuRepository
from app.domains.collection.schemas.pending_onu import PendingOnuRead


class PendingOnuService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = PendingOnuRepository(session)

    async def get(self, pending_onu_id: UUID, *, actor: Actor) -> PendingOnuRead:
        del actor
        obj = await self._repo.get_by_id(pending_onu_id)
        if obj is None:
            raise PendingOnuNotFound(pending_onu_id)
        return PendingOnuRead.model_validate(obj)

    async def list_page(
        self,
        *,
        params: PageParams,
        olt_id: UUID | None,
        pon_port_id: UUID | None,
        state: PendingOnuState | None,
        actor: Actor,
    ) -> Page[PendingOnuRead]:
        del actor
        items, total = await self._repo.list_page(
            limit=params.limit,
            offset=params.offset,
            olt_id=olt_id,
            pon_port_id=pon_port_id,
            state=state,
        )
        return Page[PendingOnuRead](
            items=[PendingOnuRead.model_validate(p) for p in items],
            total=total,
            page=params.page,
            page_size=params.page_size,
        )
