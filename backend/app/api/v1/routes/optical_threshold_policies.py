# Rotas de optical_threshold_policy.
# GET list, GET detail, POST, PATCH. Sem DELETE: pausa via active=false.

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_actor, require_admin
from app.core.actor import Actor
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_session
from app.domains.optical.enums import OpticalScopeType
from app.domains.optical.schemas.optical_threshold_policy import (
    OpticalThresholdPolicyCreate,
    OpticalThresholdPolicyRead,
    OpticalThresholdPolicyUpdate,
)
from app.domains.optical.services.optical_threshold_policy import (
    OpticalThresholdPolicyService,
)

router = APIRouter(
    prefix="/optical-threshold-policies",
    tags=["optical:threshold-policies"],
)


def get_service(
    session: AsyncSession = Depends(get_session),
) -> OpticalThresholdPolicyService:
    return OpticalThresholdPolicyService(session)


router.get(
    "",
    response_model=Page[OpticalThresholdPolicyRead],
    dependencies=[Depends(require_admin)],
)


async def list_policies(
    scope_type: OpticalScopeType | None = Query(default=None),
    metric_name: str | None = Query(default=None),
    active_only: bool = Query(default=True),
    params: PageParams = Depends(page_params),
    service: OpticalThresholdPolicyService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> Page[OpticalThresholdPolicyRead]:
    return await service.list_page(
        params=params,
        scope_type=scope_type,
        metric_name=metric_name,
        active_only=active_only,
        actor=actor,
    )


@router.get(
    "/{policy_id}",
    response_model=OpticalThresholdPolicyRead,
    dependencies=[Depends(require_admin)],
)
async def get_policy(
    policy_id: UUID,
    service: OpticalThresholdPolicyService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> OpticalThresholdPolicyRead:
    return await service.get(policy_id, actor=actor)


@router.post(
    "",
    response_model=OpticalThresholdPolicyRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
async def crate_policy(
    payload: OpticalThresholdPolicyCreate,
    service: OpticalThresholdPolicyService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> OpticalThresholdPolicyRead:
    return await service.create(payload, actor=actor)


@router.patch(
    "/{policy_id}",
    response_model=OpticalThresholdPolicyRead,
    dependencies=[Depends(require_admin)],
)
async def update_policy(
    policy_id: UUID,
    payload: OpticalThresholdPolicyUpdate,
    service: OpticalThresholdPolicyService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> OpticalThresholdPolicyRead:
    return await service.update(policy_id, payload, actor=actor)
