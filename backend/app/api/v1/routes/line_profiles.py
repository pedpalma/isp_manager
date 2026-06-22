# Rotas REST de Line Profile. Prefix com hífen (/line-profiles),
# flat com ?olt_id=. DELETE não exposto.

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_actor
from app.core.actor import Actor
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_session
from app.domains.inventory.schemas.line_profile import (
    LineProfileCreate,
    LineProfileRead,
    LineProfileUpdate,
)
from app.domains.inventory.services.line_profile import LineProfileService

router = APIRouter(prefix="/line-profiles", tags=["inventory:line_profiles"])


def get_service(session: AsyncSession = Depends(get_session)) -> LineProfileService:
    return LineProfileService(session)


@router.get("", response_model=Page[LineProfileRead])
async def list_line_profiles(
    olt_id: UUID = Query(..., description="Filtra perfis de linha por OLT."),
    params: PageParams = Depends(page_params),
    service: LineProfileService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> Page[LineProfileRead]:
    return await service.list_for_olt(olt_id, params, actor=actor)


@router.get("/{line_profile_id}", response_model=LineProfileRead)
async def get_line_profile(
    line_profile_id: UUID,
    service: LineProfileService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> LineProfileRead:
    return await service.get(line_profile_id, actor=actor)


@router.post("", response_model=LineProfileRead, status_code=status.HTTP_201_CREATED)
async def create_line_profile(
    payload: LineProfileCreate,
    service: LineProfileService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> LineProfileRead:
    return await service.create(payload, actor=actor)


@router.patch("/{line_profile_id}", response_model=LineProfileRead)
async def update_line_profile(
    line_profile_id: UUID,
    payload: LineProfileUpdate,
    service: LineProfileService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> LineProfileRead:
    return await service.update(line_profile_id, payload, actor=actor)
