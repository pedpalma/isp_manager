# Rotas REST de Manufacturer.

# Convenções (válidas para todos os routers de catálogo):
# - GET /manufacturers -> lista paginada (filtros por query string)
# - GET /manufacturers/{id} -> detalhe
# - POST /manufacturers -> criação (201 Created)
# - PATCH /manufacturers/{id} -> atualização parcial

# DELETE não é exposto. Para "desativar" um fabricante, use PATCH com
# `{"active": false}`. Apagar de verdade quebraria as FKs em olt_model,
# onu_model e olt, e a auditoria perderia rastros.

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_actor
from app.core.actor import Actor
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_session
from app.domains.inventory.schemas.manufacturer import (
    ManufacturerCreate,
    ManufacturerRead,
    ManufacturerUpdate,
)
from app.domains.inventory.services.manufacturer import ManufacturerService

router = APIRouter(prefix="/manufacturers", tags=["inventory:manufacturers"])


def get_service(
    session: AsyncSession = Depends(get_session),
) -> ManufacturerService:
    """Factory de service: lê a sessão (Depends) e injeta no service."""
    return ManufacturerService(session)


@router.get(
    "",
    response_model=Page[ManufacturerRead],
    summary="Lista fabricantes (paginada)",
)
async def list_manufacturers(
    params: PageParams = Depends(page_params),
    only_active: bool = Query(
        default=False,
        description="Se true, retorna apenas fabricantes ativos.",
    ),
    search: str | None = Query(
        default=None,
        max_length=200,
        description="Filtro `LIKE` no nome (case-insensitive).",
    ),
    service: ManufacturerService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),  # noqa: B008
) -> Page[ManufacturerRead]:
    items, total = await service.list_page(
        offset=params.offset,
        limit=params.limit,
        only_active=only_active,
        search=search,
        actor=actor,
    )
    return Page[ManufacturerRead](
        items=[ManufacturerRead.model_validate(m) for m in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get(
    "/{manufacturer_id}",
    response_model=ManufacturerRead,
    summary="Detalhe de um fabricante",
)
async def get_manufacturer(
    manufacturer_id: UUID,
    service: ManufacturerService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> ManufacturerRead:
    m = await service.get(manufacturer_id, actor=actor)
    return ManufacturerRead.model_validate(m)


@router.post(
    "",
    response_model=ManufacturerRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cria um fabricante",
)
async def create_manufacturer(
    data: ManufacturerCreate,
    service: ManufacturerService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> ManufacturerRead:
    m = await service.create(data, actor=actor)
    return ManufacturerRead.model_validate(m)


@router.patch(
    "/{manufacturer_id}",
    response_model=ManufacturerRead,
    summary="Atualiza parcialmente um fabricante",
)
async def update_manufacturer(
    manufacturer_id: UUID,
    data: ManufacturerUpdate,
    service: ManufacturerService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> ManufacturerRead:
    m = await service.update(manufacturer_id, data, actor=actor)
    return ManufacturerRead.model_validate(m)
