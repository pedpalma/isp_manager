# Rotas /api/v1/provisioning-orders.

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, require_admin
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


@router.get(
    "",
    response_model=Page[ProvisioningOrderRead],
)
async def list_provisioning_orders(
    current: Annotated[CurrentUser, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
    params: Annotated[PageParams, Depends(page_params)],
    olt_id: UUID | None = Query(default=None),
    status_filter: ProvisioningStatus | None = Query(default=None, alias="status"),
    app_user_id: UUID | None = Query(default=None),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
) -> Page[ProvisioningOrderRead]:
    service = ProvisioningOrderService(session)
    return await service.list_page(
        params=params,
        olt_id=olt_id,
        status_filter=status_filter,
        app_user_id=app_user_id,
        created_from=created_from,
        created_to=created_to,
        actor=current.to_actor(),
    )


@router.get(
    "/{provisioning_order_id}",
    response_model=ProvisioningOrderDetailRead,
)
async def get_provisioning_order(
    provisioning_order_id: UUID,
    current: Annotated[CurrentUser, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProvisioningOrderDetailRead:
    service = ProvisioningOrderService(session)
    return await service.get_detail(provisioning_order_id, actor=current.to_actor())


@router.post(
    "",
    response_model=ProvisioningOrderDetailRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_provisioning_order(
    payload: ProvisioningOrderCreate,
    current: Annotated[CurrentUser, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProvisioningOrderDetailRead:
    """Cria ordem em 'pending', commita, enfileira o worker Celery, refecha o
    detalhe atualizado e retorna. Sob task_always_eager=True (testes) o detalhe
    já reflete estado terminal (success/failed/rolled_back/partial)."""

    service = ProvisioningOrderService(session)
    actor = current.to_actor()
    order_detail = await service.create_order(payload=payload, actor=actor)

    order_id = order_detail.provisioning_order_id
    try:
        run_provisioning_order.delay(str(order_id))
    except Exception as exc:
        # Janela de órfão idêntica ao M16: commit ok + enqueue falhando
        # deixa ordem 'pending'; detect_stale_jobs marca failed após threshold.
        log.error(
            "provisioning.enqueue_failed",
            provisioning_order_id=str(order_id),
            error=str(exc),
        )

    # Refetch pós-delay para refletir estado terminal (sob eager) ou pending (prod).
    return await service.get_detail(order_id, actor=actor)
