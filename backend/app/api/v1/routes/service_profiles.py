# Rotas REST de Service Profile. Prefix com hífen (/service-profiles),
# flat com ?olt_id=. DELETE não exposto.

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_actor
from app.core.actor import Actor
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_session
from app.domains.inventory.schemas.service_profile import (
    ServiceProfileCreate,
    ServiceProfileRead,
    ServiceProfileUpdate,
)
from app.domains.inventory.services.service_profile import ServiceProfileService

router = APIRouter(prefix="/service-profiles", tags=["inventory:service_profiles"])


def get_service(
    session: AsyncSession = Depends(get_session),
) -> ServiceProfileService:
    return ServiceProfileService(session)


@router.get("", response_model=Page[ServiceProfileRead])
async def list_service_profiles(
    olt_id: UUID = Query(..., description="Filtra perfis de serviço por OLT."),
    params: PageParams = Depends(page_params),
    service: ServiceProfileService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> Page[ServiceProfileRead]:
    return await service.list_for_olt(olt_id, params, actor=actor)


@router.get("/{service_profile_id}", response_model=ServiceProfileRead)
async def get_service_profile(
    service_profile_id: UUID,
    service: ServiceProfileService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> ServiceProfileRead:
    return await service.get(service_profile_id, actor=actor)


@router.post("", response_model=ServiceProfileRead, status_code=status.HTTP_201_CREATED)
async def create_service_profile(
    payload: ServiceProfileCreate,
    service: ServiceProfileService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> ServiceProfileRead:
    return await service.create(payload, actor=actor)


@router.patch("/{service_profile_id}", response_model=ServiceProfileRead)
async def update_service_profile(
    service_profile_id: UUID,
    payload: ServiceProfileUpdate,
    service: ServiceProfileService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> ServiceProfileRead:
    return await service.update(service_profile_id, payload, actor=actor)
