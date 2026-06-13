# GET /api/v1/olts/{olt_id}/topology
# Endpoint da árvore completa. Router em arquivo próprio para não tocar em olts.py.

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_actor
from app.core.actor import Actor
from app.db.session import get_session
from app.domains.inventory.schemas.topology import OltTopology
from app.domains.inventory.services.topology import TopologyService

router = APIRouter(prefix="/olts", tags=["inventory:topology"])


def get_service(session: AsyncSession = Depends(get_session)) -> TopologyService:
    return TopologyService(session)


@router.get("/{olt_id}/topology", response_model=OltTopology)
async def get_olt_topology(
    olt_id: UUID,
    service: TopologyService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> OltTopology:
    return await service.get_for_olt(olt_id, actor=actor)
