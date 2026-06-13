# Rotas REST de PonPort. Prefix com hifen (convenção dos paths multi-palavra).

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_actor
from app.core.actor import Actor
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_session
from app.domains.inventory.schemas.pon_port import (
    PonPortCreate,
    PonPortRead,
    PonPortUpdate,
)
from app.domains.inventory.services.pon_port import PonPortService

router = APIRouter(prefix="/pon-ports", tags=["inventory:pon-ports"])


def get_service(session: AsyncSession = Depends(get_session)) -> PonPortService:
    return PonPortService(session)


@router.get("", response_model=Page[PonPortRead])
async def list_pon_ports(
    slot_id: UUID = Query(..., description="Filtra portas PON por slot."),
    params: PageParams = Depends(page_params),
    service: PonPortService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> Page[PonPortRead]:
    return await service.list_for_slot(slot_id, params, actor=actor)


@router.get("/{pon_port_id}", response_model=PonPortRead)
async def get_pon_port(
    pon_port_id: UUID,
    service: PonPortService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> PonPortRead:
    return await service.get(pon_port_id, actor=actor)


@router.post("", response_model=PonPortRead, status_code=status.HTTP_201_CREATED)
async def create_pon_port(
    payload: PonPortCreate,
    service: PonPortService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> PonPortRead:
    return await service.create(payload, actor=actor)


@router.patch("/{pon_port_id}", response_model=PonPortRead)
async def update_pon_port(
    pon_port_id: UUID,
    payload: PonPortUpdate,
    service: PonPortService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> PonPortRead:
    return await service.update(pon_port_id, payload, actor=actor)
