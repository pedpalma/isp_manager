# Rotas REST de Chassis.

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_actor
from app.core.actor import Actor
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_session
from app.domains.inventory.schemas.chassis import (
    ChassisCreate,
    ChassisRead,
    ChassisUpdate,
)
from app.domains.inventory.services.chassis import ChassisService

router = APIRouter(prefix="/chassis", tags=["inventory:chassis"])


def get_service(session: AsyncSession = Depends(get_session)) -> ChassisService:
    return ChassisService(session)


@router.get("", response_model=Page[ChassisRead])
async def list_chassis(
    olt_id: UUID = Query(..., description="Filtra chassis por OLT."),
    params: PageParams = Depends(page_params),
    service: ChassisService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> Page[ChassisRead]:
    return await service.list_for_olt(olt_id, params, actor=actor)


@router.get("/{chassis_id}", response_model=ChassisRead)
async def get_chassis(
    chassis_id: UUID,
    service: ChassisService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> ChassisRead:
    return await service.get(chassis_id, actor=actor)


@router.post("", response_model=ChassisRead, status_code=status.HTTP_201_CREATED)
async def create_chassis(
    payload: ChassisCreate,
    service: ChassisService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> ChassisRead:
    return await service.create(payload, actor=actor)


@router.patch("/{chassis_id}", response_model=ChassisRead)
async def update_chassis(
    chassis_id: UUID,
    payload: ChassisUpdate,
    service: ChassisService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> ChassisRead:
    return await service.update(chassis_id, payload, actor=actor)
