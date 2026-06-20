# Rotas de usuários do sistema (somente admin).
# CRUD sem DELETE.

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, require_admin
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_session
from app.domains.auth.schemas.app_user import (
    AppUserCreate,
    AppUserRead,
    AppUserUpdate,
)
from app.domains.auth.services.app_user import AppUserService

router = APIRouter(prefix="/app-users", tags=["auth:app-users"])


def get_app_user_service(
    session: AsyncSession = Depends(get_session),
) -> AppUserService:
    return AppUserService(session)


@router.get("", response_model=Page[AppUserRead])
async def list_app_users(
    only_active: bool = Query(default=False),
    user_group_id: UUID | None = Query(default=None),
    search: str | None = Query(default=None),
    params: PageParams = Depends(page_params),
    current: CurrentUser = Depends(require_admin),
    service: AppUserService = Depends(get_app_user_service),
) -> Page[AppUserRead]:
    items, total = await service.list_page(
        offset=params.offset,
        limit=params.limit,
        only_active=only_active,
        user_group_id=user_group_id,
        search=search,
        actor=current.to_actor(),
    )
    return Page[AppUserRead](
        items=[AppUserRead.model_validate(i) for i in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get("/{app_user_id}", response_model=AppUserRead)
async def get_app_user(
    app_user_id: UUID,
    current: CurrentUser = Depends(require_admin),
    service: AppUserService = Depends(get_app_user_service),
) -> AppUserRead:
    u = await service.get(app_user_id, actor=current.to_actor())
    return AppUserRead.model_validate(u)


@router.post("", response_model=AppUserRead, status_code=status.HTTP_201_CREATED)
async def create_app_user(
    payload: AppUserCreate,
    current: CurrentUser = Depends(require_admin),
    service: AppUserService = Depends(get_app_user_service),
) -> AppUserRead:
    u = await service.create(payload, actor=current.to_actor())
    return AppUserRead.model_validate(u)


@router.patch("/{app_user_id}", response_model=AppUserRead)
async def update_app_user(
    app_user_id: UUID,
    payload: AppUserUpdate,
    current: CurrentUser = Depends(require_admin),
    service: AppUserService = Depends(get_app_user_service),
) -> AppUserRead:
    u = await service.update(app_user_id, payload, actor=current.to_actor())
    return AppUserRead.model_validate(u)
