# Rotas /api/v1/olt-command-profiles.

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, require_admin
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_session
from app.domains.inventory.enums import AccessProtocol
from app.domains.provisioning.schemas.olt_command_profile import (
    OltCommandProfileCreate,
    OltCommandProfileRead,
    OltCommandProfileUpdate,
)
from app.domains.provisioning.services.olt_command_profile import (
    OltCommandProfileService,
)

router = APIRouter(
    prefix="/olt-command-profiles",
    tags=["provisioning:olt-command-profiles"],
)


@router.post(
    "",
    response_model=OltCommandProfileRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_olt_command_profile(
    payload: OltCommandProfileCreate,
    current: Annotated[CurrentUser, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OltCommandProfileRead:
    service = OltCommandProfileService(session)
    return await service.create(payload, actor=current.to_actor())


@router.get(
    "",
    response_model=Page[OltCommandProfileRead],
)
async def list_olt_command_profiles(
    current: Annotated[CurrentUser, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
    params: Annotated[PageParams, Depends(page_params)],
    olt_model_id: UUID | None = None,
    access_protocol: AccessProtocol | None = None,
    active: bool | None = None,
) -> Page[OltCommandProfileRead]:
    service = OltCommandProfileService(session)
    return await service.list_page(
        params=params,
        olt_model_id=olt_model_id,
        access_protocol=access_protocol,
        active=active,
        actor=current.to_actor(),
    )


@router.get(
    "/{olt_command_profile_id}",
    response_model=OltCommandProfileRead,
)
async def get_olt_command_profile(
    olt_command_profile_id: UUID,
    current: Annotated[CurrentUser, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OltCommandProfileRead:
    service = OltCommandProfileService(session)
    return await service.get(olt_command_profile_id, actor=current.to_actor())


@router.patch(
    "/{olt_command_profile_id}",
    response_model=OltCommandProfileRead,
)
async def update_olt_command_profile(
    olt_command_profile_id: UUID,
    payload: OltCommandProfileUpdate,
    current: Annotated[CurrentUser, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OltCommandProfileRead:
    service = OltCommandProfileService(session)
    return await service.update(
        olt_command_profile_id,
        payload,
        actor=current.to_actor(),
    )
