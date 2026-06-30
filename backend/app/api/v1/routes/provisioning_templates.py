# Rotas /api/v1/provisioning-templates.

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, require_admin
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_session
from app.domains.provisioning.schemas.provisioning_template import (
    ProvisioningTemplateCreate,
    ProvisioningTemplateRead,
    ProvisioningTemplateUpdate,
)
from app.domains.provisioning.services.provisioning_template import (
    ProvisioningTemplateService,
)

router = APIRouter(prefix="/provisioning-templates", tags=["provisioning-templates"])


@router.post(
    "",
    response_model=ProvisioningTemplateRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_provisioning_template(
    payload: ProvisioningTemplateCreate,
    current: Annotated[CurrentUser, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProvisioningTemplateRead:
    service = ProvisioningTemplateService(session)
    return await service.create(
        payload,
        actor=current.to_actor(),
        created_by_user_id=current.app_user_id,
    )


@router.get(
    "/{provisioning_template_id}",
    response_model=ProvisioningTemplateRead,
)
async def get_provisioning_template(
    provisioning_template_id: UUID,
    current: Annotated[CurrentUser, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProvisioningTemplateRead:
    del current  # auth-only; sem uso direto na consulta
    service = ProvisioningTemplateService(session)
    return await service.get(provisioning_template_id)


@router.get(
    "",
    response_model=Page[ProvisioningTemplateRead],
)
async def list_provisioning_templates(
    current: Annotated[CurrentUser, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
    params: Annotated[PageParams, Depends(page_params)],
    manufacturer_id: UUID | None = None,
    olt_model_id: UUID | None = None,
    template_scope: str | None = None,
    active: bool | None = None,
) -> Page[ProvisioningTemplateRead]:
    del current
    service = ProvisioningTemplateService(session)
    items, total = await service.list_page(
        offset=params.offset,
        limit=params.limit,
        manufacturer_id=manufacturer_id,
        olt_model_id=olt_model_id,
        template_scope=template_scope,
        active=active,
    )
    return Page[ProvisioningTemplateRead](
        items=items,
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.patch(
    "/{provisioning_template_id}",
    response_model=ProvisioningTemplateRead,
)
async def update_provisioning_template(
    provisioning_template_id: UUID,
    payload: ProvisioningTemplateUpdate,
    current: Annotated[CurrentUser, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProvisioningTemplateRead:
    service = ProvisioningTemplateService(session)
    return await service.update(
        provisioning_template_id,
        payload,
        actor=current.to_actor(),
    )
