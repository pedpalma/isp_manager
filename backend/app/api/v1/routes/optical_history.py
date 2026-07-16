# Rota de leitura do histórico óptico de uma ONU.
# GET /api/v1/onus/{onu_id}/optical-history?from=...&to=...&page=...
# Filtros temporais opcionais; service aplica default
# (NOW() - 30 dias) para garantir partition pruning.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, require_admin
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_session
from app.domains.optical.schemas.optical_reading import OpticalReadingRead
from app.domains.optical.services.optical_history import OpticalHistoryService

router = APIRouter(prefix="/onus", tags=["optical:history"])


def get_service(session: AsyncSession = Depends(get_session)) -> OpticalHistoryService:
    return OpticalHistoryService(session)


@router.get(
    "/{onu_id}/optical-history",
    response_model=Page[OpticalReadingRead],
)
async def list_optical_history(
    onu_id: UUID,
    date_from: datetime | None = Query(default=None, alias="from"),
    date_to: datetime | None = Query(default=None, alias="to"),
    params: PageParams = Depends(page_params),
    service: OpticalHistoryService = Depends(get_service),
    current: CurrentUser = Depends(require_admin),
) -> Page[OpticalReadingRead]:
    return await service.list_for_onu(
        onu_id=onu_id,
        params=params,
        date_from=date_from,
        date_to=date_to,
        actor=current.to_actor(),
    )
