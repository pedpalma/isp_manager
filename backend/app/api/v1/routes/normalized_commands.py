# Rotas /api/v1/normalized-commands.

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, require_admin
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_session
from app.domains.provisioning.schemas.normalized_command import (
    NormalizedCommandCreate,
    NormalizedCommandRead,
    NormalizedCommandUpdate,
)
from app.domains.provisioning.services.normalized_command import (
    NormalizedCommandService,
)

router = APIRouter(prefix="/normalized-commands", tags=["normalized-commands"])


@router.post(
    "",
    response_model=NormalizedCommandRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_normalized_command(
    payload: NormalizedCommandCreate,
    current: Annotated[CurrentUser, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> NormalizedCommandRead:
    service = NormalizedCommandService(session)
    return await service.create(payload, actor=current.to_actor())


@router.get(
    "/{normalized_command_id}",
    response_model=NormalizedCommandRead,
)
async def get_normalized_command(
    normalized_command_id: UUID,
    current: Annotated[CurrentUser, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> NormalizedCommandRead:
    del current
    service = NormalizedCommandService(session)
    return await service.get(normalized_command_id)


@router.get(
    "",
    response_model=Page[NormalizedCommandRead],
)
async def list_normalized_commands(
    current: Annotated[CurrentUser, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
    params: Annotated[PageParams, Depends(page_params)],
    manufacturer_id: UUID | None = None,
    olt_model_id: UUID | None = None,
    command_key: str | None = None,
    command_type: str | None = None,
    active: bool | None = None,
) -> Page[NormalizedCommandRead]:
    del current
    service = NormalizedCommandService(session)
    items, total = await service.list_page(
        offset=params.offset,
        limit=params.limit,
        manufacturer_id=manufacturer_id,
        olt_model_id=olt_model_id,
        command_key=command_key,
        command_type=command_type,
        active=active,
    )
    return Page[NormalizedCommandRead](
        items=items,
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.patch(
    "/{normalized_command_id}",
    response_model=NormalizedCommandRead,
)
async def update_normalized_command(
    normalized_command_id: UUID,
    payload: NormalizedCommandUpdate,
    current: Annotated[CurrentUser, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> NormalizedCommandRead:
    service = NormalizedCommandService(session)
    return await service.update(
        normalized_command_id,
        payload,
        actor=current.to_actor(),
    )
