# Rotas de grupos de usuários (somente admin).
# CRUD sem DELETE.

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, require_admin
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_session
from app.domains.auth.schemas.user_group import (
    UserGroupCreate,
    UserGroupRead,
    UserGroupUpdate,
)
from app.domains.auth.services.user_group import UserGroupService

router = APIRouter(prefix="/user-groups", tags=["auth:user-groups"])


def get_user_group_service(
    session: AsyncSession = Depends(get_session),
) -> UserGroupService:
    return UserGroupService(session)


@router.get("", response_model=Page[UserGroupRead])
async def list_user_groups(
    only_active: bool = Query(default=False),
    params: PageParams = Depends(page_params),
    current: CurrentUser = Depends(require_admin),
    service: UserGroupService = Depends(get_user_group_service),
) -> Page[UserGroupRead]:
    items, total = await service.list_page(
        offset=params.offset,
        limit=params.limit,
        only_active=only_active,
        actor=current.to_actor(),
    )
    return Page[UserGroupRead](
        items=[UserGroupRead.model_validate(i) for i in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get("/{user_group_id}", response_model=UserGroupRead)
async def get_user_group(
    user_group_id: UUID,
    current: CurrentUser = Depends(require_admin),
    service: UserGroupService = Depends(get_user_group_service),
) -> UserGroupRead:
    g = await service.get(user_group_id, actor=current.to_actor())
    return UserGroupRead.model_validate(g)


@router.post("", response_model=UserGroupRead, status_code=status.HTTP_201_CREATED)
async def create_user_group(
    payload: UserGroupCreate,
    current: CurrentUser = Depends(require_admin),
    service: UserGroupService = Depends(get_user_group_service),
) -> UserGroupRead:
    g = await service.create(payload, actor=current.to_actor())
    return UserGroupRead.model_validate(g)


@router.patch("/{user_group_id}", response_model=UserGroupRead)
async def update_user_group(
    user_group_id: UUID,
    payload: UserGroupUpdate,
    current: CurrentUser = Depends(require_admin),
    service: UserGroupService = Depends(get_user_group_service),
) -> UserGroupRead:
    g = await service.update(user_group_id, payload, actor=current.to_actor())
    return UserGroupRead.model_validate(g)
