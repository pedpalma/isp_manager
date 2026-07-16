# Rota de diagnóstico de thresholds efetivos
# GET /api/v1/onus/{onu_id}/effective-thresholds
# Mostra qual policy está sendo aplicada após a resolução hierárquica

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, require_admin
from app.db.session import get_session
from app.domains.optical.schemas.effective_thresholds import (
    EffectiveThresholdsRead,
)
from app.domains.optical.services.effective_thresholds import (
    EffectiveThresholdsService,
)

router = APIRouter(prefix="/onus", tags=["optical:effective-thresholds"])


def get_service(
    session: AsyncSession = Depends(get_session),
) -> EffectiveThresholdsService:
    return EffectiveThresholdsService(session)


@router.get(
    "/{onu_id}/effective-thresholds",
    response_model=EffectiveThresholdsRead,
)
async def get_effective_thresholds(
    onu_id: UUID,
    service: EffectiveThresholdsService = Depends(get_service),
    current: CurrentUser = Depends(require_admin),
) -> EffectiveThresholdsRead:
    return await service.get_for_onu(onu_id, actor=current.to_actor())
