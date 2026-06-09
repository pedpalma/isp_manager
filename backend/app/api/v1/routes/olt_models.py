# Rotas REST de OltModel.

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_actor
from app.core.actor import Actor
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_session
from app.domains.inventory.schemas.olt_model import (
    OltModelCreate,
    OltModelRead,
    OltModelUpdate,
)
from app.domains.inventory.services.olt_model import OltModelService

router = APIRouter(prefix="/olt-models", tags=["inventory:olt-models"])


def get_service(session: AsyncSession = Depends(get_session)) -> OltModelService:
    return OltModelService(session)


@router.get(
    "",
    response_model=Page[OltModelRead],
    summary="Lista modelos de OLT (paginada)",
)
async def list_olt_models(
    params: PageParams = Depends(page_params),
    only_active: bool = Query(default=False),
    manufacturer_id: UUID | None = Query(
        default=None,
        description="Filtra por fabricante.",
    ),
    search: str | None = Query(
        default=None,
        max_length=200,
        description="Filtro `LIKE` no nome do modelo (case-insensitive).",
    ),
    service: OltModelService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> Page[OltModelRead]:
    items, total = await service.list_page(
        offset=params.offset,
        limit=params.limit,
        only_active=only_active,
        manufacturer_id=manufacturer_id,
        search=search,
        actor=actor,
    )
    return Page[OltModelRead](
        items=[OltModelRead.model_validate(m) for m in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get("/{olt_model_id}", response_model=OltModelRead)
async def get_olt_model(
    olt_model_id: UUID,
    service: OltModelService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> OltModelRead:
    m = await service.get(olt_model_id, actor=actor)
    return OltModelRead.model_validate(m)


@router.post(
    "",
    response_model=OltModelRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_olt_model(
    data: OltModelCreate,
    service: OltModelService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> OltModelRead:
    m = await service.create(data, actor=actor)
    return OltModelRead.model_validate(m)


@router.patch("/{olt_model_id}", response_model=OltModelRead)
async def update_olt_model(
    olt_model_id: UUID,
    data: OltModelUpdate,
    service: OltModelService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> OltModelRead:
    m = await service.update(olt_model_id, data, actor=actor)
    return OltModelRead.model_validate(m)
