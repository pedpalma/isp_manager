# Rotas de alertas ópticos.
# GET /api/v1/optical-alerts (lista paginada com filtros)
# GET /api/v1/optical-alerts/{id} (detalhe)
# POST /api/v1/optical-alerts/{id}/acknowledge
# POST /api/v1/optical-alerts/{id}/resolve
# Sem DELETE: alertas são registro histórico.

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, require_admin
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_session
from app.domains.optical.enums import OpticalAlertStatus, OpticalSeverity
from app.domains.optical.schemas.optical_alert_event import OpticalAlertEventRead
from app.domains.optical.services.optical_alert import OpticalAlertService

router = APIRouter(prefix="/optical-alerts", tags=["optical:alerts"])


def get_service(session: AsyncSession = Depends(get_session)) -> OpticalAlertService:
    return OpticalAlertService(session)


@router.get(
    "",
    response_model=Page[OpticalAlertEventRead],
)
async def list_optical_alerts(
    olt_id: UUID | None = Query(default=None),
    onu_id: UUID | None = Query(default=None),
    status_filter: OpticalAlertStatus | None = Query(default=None, alias="status"),
    severity: OpticalSeverity | None = Query(default=None),
    params: PageParams = Depends(page_params),
    service: OpticalAlertService = Depends(get_service),
    current: CurrentUser = Depends(require_admin),
) -> Page[OpticalAlertEventRead]:
    return await service.list_page(
        params=params,
        olt_id=olt_id,
        onu_id=onu_id,
        status_filter=status_filter,
        severity_filter=severity,
        actor=current.to_actor(),
    )


@router.get(
    "/{alert_id}",
    response_model=OpticalAlertEventRead,
)
async def get_optical_alert(
    alert_id: UUID,
    service: OpticalAlertService = Depends(get_service),
    current: CurrentUser = Depends(require_admin),
) -> OpticalAlertEventRead:
    return await service.get(alert_id, actor=current.to_actor())


@router.post(
    "/{alert_id}/acknowledge",
    response_model=OpticalAlertEventRead,
)
async def acknowledge_optical_alert(
    alert_id: UUID,
    service: OpticalAlertService = Depends(get_service),
    current: CurrentUser = Depends(require_admin),
) -> OpticalAlertEventRead:
    return await service.acknowledge(alert_id, actor=current.to_actor())


@router.post(
    "/{alert_id}/resolve",
    response_model=OpticalAlertEventRead,
)
async def resolve_optical_alert(
    alert_id: UUID,
    service: OpticalAlertService = Depends(get_service),
    current: CurrentUser = Depends(require_admin),
) -> OpticalAlertEventRead:
    return await service.resolve(alert_id, actor=current.to_actor())
