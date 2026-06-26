# Rotas de optical_threshold_policy.
# GET list, GET detail, POST, PATCH. Sem DELETE: pausa via active=false.

# Reescrita seguindo o padrão exato de user_groups.py (M15):
#   - require_admin como parâmetro `current: CurrentUser`, não como
#     dependencies=[] no decorator;
#   - service.list_page retorna (items, total) tupla; handler monta Page;
#   - actor obtido via current.to_actor() (sem dep separada de
#     get_current_actor).
# A versão original do M17 misturava dois padrões (dependencies=[] no
# decorator + actor via get_current_actor); embora válido em FastAPI e
# funcionando em collection_jobs.py (M16), test_list_with_filters
# reportou 405 nesta rota especificamente. Replicar o padrão user_groups
# por completo elimina qualquer variável.

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, require_admin
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


@router.get("", response_model=Page[OpticalThresholdPolicyRead])
async def list_policies(
    scope_type: OpticalScopeType | None = Query(default=None),
    metric_name: str | None = Query(default=None),
    active_only: bool = Query(default=True),
    params: PageParams = Depends(page_params),
    current: CurrentUser = Depends(require_admin),
    service: OpticalThresholdPolicyService = Depends(get_service),
) -> Page[OpticalThresholdPolicyRead]:
    return await service.list_page(
        params=params,
        scope_type=scope_type,
        metric_name=metric_name,
        active_only=active_only,
        actor=current.to_actor(),
    )


@router.get("/{policy_id}", response_model=OpticalThresholdPolicyRead)
async def get_policy(
    policy_id: UUID,
    current: CurrentUser = Depends(require_admin),
    service: OpticalThresholdPolicyService = Depends(get_service),
) -> OpticalThresholdPolicyRead:
    return await service.get(policy_id, actor=current.to_actor())


@router.post(
    "",
    response_model=OpticalThresholdPolicyRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_policy(
    payload: OpticalThresholdPolicyCreate,
    current: CurrentUser = Depends(require_admin),
    service: OpticalThresholdPolicyService = Depends(get_service),
) -> OpticalThresholdPolicyRead:
    return await service.create(payload, actor=current.to_actor())


@router.patch("/{policy_id}", response_model=OpticalThresholdPolicyRead)
async def update_policy(
    policy_id: UUID,
    payload: OpticalThresholdPolicyUpdate,
    current: CurrentUser = Depends(require_admin),
    service: OpticalThresholdPolicyService = Depends(get_service),
) -> OpticalThresholdPolicyRead:
    return await service.update(policy_id, payload, actor=current.to_actor())
