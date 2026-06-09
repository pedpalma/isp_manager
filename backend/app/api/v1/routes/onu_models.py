# Rotas REST de OnuModel.

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_actor
from app.core.actor import Actor
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_session
from app.domains.inventory.schemas.onu_model import (
    OnuModelCreate,
    OnuModelRead,
    OnuModelUpdate,
)
from app.domains.inventory.services.onu_model import OnuModelService

router = APIRouter(prefix="/onu-models", tags=["inventory:onu-models"])


def get_service(session: AsyncSession = Depends(get_session)) -> OnuModelService:
    return OnuModelService(session)


@router.get(
    "",
    response_model=Page[OnuModelRead],
    summary="Lista modelos de ONU (paginada)",
)
async def list_onu_models(
    params: PageParams = Depends(page_params),
    only_active: bool = Query(default=False),
    manufacturer_id: UUID | None = Query(default=None),
    category: str | None = Query(
        default=None,
        max_length=100,
        description="Filtro exato por categoria.",
    ),
    search: str | None = Query(
        default=None,
        max_length=200,
        description="Filtro `LIKE` no nome do modelo (case-insensitive).",
    ),
    service: OnuModelService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> Page[OnuModelRead]:
    items, total = await service.list_page(
        offset=params.offset,
        limit=params.limit,
        only_active=only_active,
        manufacturer_id=manufacturer_id,
        category=category,
        search=search,
        actor=actor,
    )
    return Page[OnuModelRead](
        items=[OnuModelRead.model_validate(m) for m in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get("/{onu_model_id}", response_model=OnuModelRead)
async def get_onu_model(
    onu_model_id: UUID,
    service: OnuModelService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> OnuModelRead:
    m = await service.get(onu_model_id, actor=actor)
    return OnuModelRead.model_validate(m)


@router.post(
    "",
    response_model=OnuModelRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_onu_model(
    data: OnuModelCreate,
    service: OnuModelService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> OnuModelRead:
    m = await service.create(data, actor=actor)
    return OnuModelRead.model_validate(m)


@router.patch("/{onu_model_id}", response_model=OnuModelRead)
async def update_onu_model(
    onu_model_id: UUID,
    data: OnuModelUpdate,
    service: OnuModelService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> OnuModelRead:
    m = await service.update(onu_model_id, data, actor=actor)
    return OnuModelRead.model_validate(m)
