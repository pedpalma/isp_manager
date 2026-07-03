# Rotas /api/v1/provisioning-orders.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_actor, require_admin
from app.core.actor import Actor
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_session
from app.domains.provisioning.enums import ProvisioningStatus
from app.domains.provisioning.schemas.provisioning_order import (
    ProvisioningOrderCreate,
    ProvisioningOrderDetailRead,
    ProvisioningOrderRead,
)
from app.domains.provisioning.services.provisioning_order_service import (
    ProvisioningOrderService,
)
from app.tasks.provisioning import run_provisioning_order

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/provisioning-orders", tags=["provisioning:orders"])


def get_service(session: AsyncSession = Depends(get_session)) -> ProvisioningOrderService:
    return ProvisioningOrderService(session)


@router.get(
    "",
    response_model=Page[ProvisioningOrderRead],
    dependencies=[Depends(require_admin)],
)
async def list_provisioning_orders(
    olt_id: UUID | None = Query(default=None),
    status_filter: ProvisioningStatus | None = Query(default=None, alias="status"),
    app_user_id: UUID | None = Query(default=None),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    params: PageParams = Depends(page_params),
    service: ProvisioningOrderService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> Page[ProvisioningOrderRead]:
    return await service.list_page(
        params=params,
        olt_id=olt_id,
        status_filter=status_filter,
        app_user_id=app_user_id,
        created_from=created_from,
        created_to=created_to,
        actor=actor,
    )


@router.get(
    "/{provisioning_order_id}",
    response_model=ProvisioningOrderDetailRead,
    dependencies=[Depends(require_admin)],
)
async def get_provisioning_order(
    provisioning_order_id: UUID,
    service: ProvisioningOrderService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> ProvisioningOrderDetailRead:
    return await service.get_detail(provisioning_order_id, actor=actor)


@router.post(
    "",
    response_model=ProvisioningOrderDetailRead,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_admin)],
)
async def create_provisioning_order(
    payload: ProvisioningOrderCreate,
    service: ProvisioningOrderService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> ProvisioningOrderDetailRead:
    """Cria ordem em 'pending', commita, enfileira o worker Celery, refecha o
    detalhe atualizado e retorna. Sob task_always_eager=True (testes) o detalhe
    já reflete estado terminal (success/failed/rolled_back/partial)."""

    order_detail = await service.create_order(payload=payload, actor=actor)

    order_id = order_detail.provisioning_order_id
    try:
        run_provisioning_order.delay(str(order_id))
    except Exception as exc:
        log.error(
            "provisioning.enqueue_failed",
            provisioning_order_id=str(order_id),
            error=str(exc),
        )

    # Refetch pós-delay para refletir estado terminal (sob eager) ou pending (prod).
    return await service.get_detail(order_id, actor=actor)
