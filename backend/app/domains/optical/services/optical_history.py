# Service de leitura do histórico óptico de uma ONU.
# Read-only: leituras nascem do worker (sessão sync).
# Valida que a ONU exista e não esteja soft-deletada antes de listar
# (404 vs lista vazia). Listagem usa filtro temporal default para
# garantir partition pruning.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.pagination import Page, PageParams
from app.domains.inventory.exceptions import OnuNotFound
from app.domains.inventory.repositories.onu import OnuRepository
from app.domains.optical.repositories.optical_reading import (
    OpticalReadingRepository,
)
from app.domains.optical.schemas.optical_reading import OpticalReadingRead


class OpticalHistoryService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = OpticalReadingRepository(session)
        self._onu_repo = OnuRepository(session)

    async def list_for_onu(
        self,
        *,
        onu_id: UUID,
        params: PageParams,
        date_from: datetime | None,
        date_to: datetime | None,
        actor: Actor,
    ) -> Page[OpticalReadingRead]:
        del actor
        # 404 quando a ONU não existe ou foi soft-deletada.
        onu = await self._onu_repo.get_by_id(onu_id)
        if onu is None:
            raise OnuNotFound(onu_id)

        items, total = await self._repo.list_for_onu(
            onu_id=onu_id,
            offset=params.offset,
            limit=params.limit,
            date_from=date_from,
            date_to=date_to,
        )
        return Page[OpticalReadingRead](
            items=[OpticalReadingRead.model_validate(r) for r in items],
            total=total,
            page=params.page,
            page_size=params.page_size,
        )
