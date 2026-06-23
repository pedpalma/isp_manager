# Rotas /api/v1/pending-onus.

# Escrita acontece via worker. Filtros opcionais:
# olt_id, pon_port_id, state. Diferente dos olt_children, pending_onu
# carrega olt_id direto, então olt_id NÃO é escopo obrigatório.

# Todas as rotas exigem JWT + require_admin.

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, require_admin
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_session
from app.domains.collection.enums import PendingOnuState
from app.domains.collection.schemas.pending_onu import PendingOnuRead
from app.domains.collection.services.pending_onu import PendingOnuService

router = APIRouter(prefix="/pending-onus", tags=["collection:pending-onus"])


def get_pending_onu_service(
    session: AsyncSession = Depends(get_session),
) -> PendingOnuService:
    return PendingOnuService(session)


@router.get("", response_model=Page[PendingOnuRead])
async def list_pending_onus(
    olt_id: UUID | None = Query(default=None),
    pon_port_id: UUID | None = Query(default=None),
    state: PendingOnuState | None = Query(default=None),
    params: PageParams = Depends(page_params),
    current: CurrentUser = Depends(require_admin),
    service: PendingOnuService = Depends(get_pending_onu_service),
) -> Page[PendingOnuRead]:
    return await service.list_page(
        params=params,
        olt_id=olt_id,
        pon_port_id=pon_port_id,
        state=state,
        actor=current.to_actor(),
    )


@router.get("/{pending_onu_id}", response_model=PendingOnuRead)
async def get_pending_onu(
    pending_onu_id: UUID,
    current: CurrentUser = Depends(require_admin),
    service: PendingOnuService = Depends(get_pending_onu_service),
) -> PendingOnuRead:
    return await service.get(pending_onu_id, actor=current.to_actor())
