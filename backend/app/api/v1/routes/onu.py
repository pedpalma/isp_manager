# Rotas REST de ONU.

# Convenções:
# - GET /onus -> lista paginada (filtros opcionais por query)
# - GET /onus/{id} -> detalhe (inclui runtime)
# - POST /onus -> criação (201 Created; resposta inclui runtime)
# - PATCH /onus/{id} -> atualização parcial (resposta inclui runtime)
# - DELETE /onus/{id} -> soft delete (204 No Content; libera serial e index)

# A ONU segue a forma da OLT (soft-delete de primeira classe): a LISTA usa
# Page[OnuRead] (sem runtime, mais barato) e aceita filtros opcionais e
# combináveis; o DETALHE/POST/PATCH usam OnuDetailRead (com runtime).

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_actor
from app.core.actor import Actor
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_session
from app.domains.inventory.schemas.onu import (
    OnuCreate,
    OnuDetailRead,
    OnuRead,
    OnuUpdate,
)
from app.domains.inventory.services.onu import OnuService

router = APIRouter(prefix="/onus", tags=["inventory:onus"])


def get_service(
    session: AsyncSession = Depends(get_session),
) -> OnuService:
    return OnuService(session)


@router.get(
    "",
    response_model=Page[OnuRead],
    summary="Lista ONUs (paginada)",
)
async def list_onus(
    params: PageParams = Depends(page_params),
    pon_port_id: UUID | None = Query(
        default=None,
        description="Filtra ONUs desta porta PON.",
    ),
    serial: str | None = Query(
        default=None,
        max_length=64,
        description="Busca por serial (parcial, case-insensitive).",
    ),
    service: OnuService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> Page[OnuRead]:
    items, total = await service.list_page(
        offset=params.offset,
        limit=params.limit,
        pon_port_id=pon_port_id,
        serial=serial,
        actor=actor,
    )
    return Page[OnuRead](
        items=[OnuRead.model_validate(o) for o in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get(
    "/{onu_id}",
    response_model=OnuDetailRead,
    summary="Detalhe de uma ONU (inclui estado operacional)",
)
async def get_onu(
    onu_id: UUID,
    service: OnuService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> OnuDetailRead:
    return await service.get(onu_id, actor=actor)


@router.post(
    "",
    response_model=OnuDetailRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cria uma ONU",
)
async def create_onu(
    data: OnuCreate,
    service: OnuService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> OnuDetailRead:
    return await service.create(data, actor=actor)


@router.patch(
    "/{onu_id}",
    response_model=OnuDetailRead,
    summary="Atualiza parcialmente uma ONU (onu_index, description)",
)
async def update_onu(
    onu_id: UUID,
    data: OnuUpdate,
    service: OnuService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> OnuDetailRead:
    return await service.update(onu_id, data, actor=actor)


@router.delete(
    "/{onu_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete de uma ONU (libera serial e índice na PON)",
)
async def delete_onu(
    onu_id: UUID,
    service: OnuService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> None:
    await service.soft_delete(onu_id, actor=actor)
    return None
