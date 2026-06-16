# Rotas REST de VLAN. Flat com ?olt_id=. DELETE nao exposto.

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_actor
from app.core.actor import Actor
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_session
from app.domains.inventory.schemas.vlan import VlanCreate, VlanRead, VlanUpdate
from app.domains.inventory.services.vlan import VlanService

router = APIRouter(prefix="/vlans", tags=["inventory:vlans"])


def get_service(session: AsyncSession = Depends(get_session)) -> VlanService:
    return VlanService(session)


@router.get("", response_model=Page[VlanRead])
async def list_vlans(
    olt_id: UUID = Query(..., description="Filtra VLANs por OLT."),
    params: PageParams = Depends(page_params),
    service: VlanService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> Page[VlanRead]:
    return await service.list_for_olt(olt_id, params, actor=actor)


@router.get("/{vlan_id}", response_model=VlanRead)
async def get_vlan(
    vlan_id: UUID,
    service: VlanService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> VlanRead:
    return await service.get(vlan_id, actor=actor)


@router.post("", response_model=VlanRead, status_code=status.HTTP_201_CREATED)
async def create_vlan(
    payload: VlanCreate,
    service: VlanService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> VlanRead:
    return await service.create(payload, actor=actor)


@router.patch("/{vlan_id}", response_model=VlanRead)
async def update_vlan(
    vlan_id: UUID,
    payload: VlanUpdate,
    service: VlanService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> VlanRead:
    return await service.update(vlan_id, payload, actor=actor)
