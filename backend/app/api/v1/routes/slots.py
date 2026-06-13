# Rotas REST de Slot.

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_actor
from app.core.actor import Actor
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_session
from app.domains.inventory.schemas.slot import SlotCreate, SlotRead, SlotUpdate
from app.domains.inventory.services.slot import SlotService

router = APIRouter(prefix="/slots", tags=["inventory:slots"])


def get_service(session: AsyncSession = Depends(get_session)) -> SlotService:
    return SlotService(session)


@router.get("", response_model=Page[SlotRead])
async def list_slots(
    chassis_id: UUID = Query(..., description="Filtra slots por chassis."),
    params: PageParams = Depends(page_params),
    service: SlotService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> Page[SlotRead]:
    return await service.list_for_chassis(chassis_id, params, actor=actor)


@router.get("/{slot_id}", response_model=SlotRead)
async def get_slot(
    slot_id: UUID,
    service: SlotService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> SlotRead:
    return await service.get(slot_id, actor=actor)


@router.post("", response_model=SlotRead, status_code=status.HTTP_201_CREATED)
async def create_slot(
    payload: SlotCreate,
    service: SlotService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> SlotRead:
    return await service.create(payload, actor=actor)


@router.patch("/{slot_id}", response_model=SlotRead)
async def update_slot(
    slot_id: UUID,
    payload: SlotUpdate,
    service: SlotService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> SlotRead:
    return await service.update(slot_id, payload, actor=actor)
