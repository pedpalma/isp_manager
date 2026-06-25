# Service de diagnostico de thresholds efetivos por ONU.
# Resolve hierarquia (onu > pon_port > olt > global) em UMA query devolve dict.
# None significa "sem politica aplicável".
# NÃO usa o ThresholdCache: este e endpoint de inspeção do operador,
# precisa devolver estado atual exato (sem stale ate 60s).

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.domains.inventory.exceptions import OnuNotFound
from app.domains.inventory.models.chassis import Chassis
from app.domains.inventory.models.onu import Onu
from app.domains.inventory.models.pon_port import PonPort
from app.domains.inventory.models.slot import Slot
from app.domains.inventory.repositories.onu import OnuRepository
from app.domains.optical.repositories.optical_threshold_policy import (
    OpticalThresholdPolicyRepository,
)
from app.domains.optical.schemas.effective_thresholds import (
    EffectiveThresholdsRead,
)
from app.domains.optical.services.threshold_cache import resolve_policies_for_onu


class EffectiveThresholdsService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._policy_repo = OpticalThresholdPolicyRepository(session)
        self._onu_repo = OnuRepository(session)

    async def get_for_onu(self, onu_id: UUID, *, actor: Actor) -> EffectiveThresholdsRead:
        del actor
        onu = await self._onu_repo.get_by_id(onu_id)
        if onu is None:
            raise OnuNotFound(onu_id)

        # Para encontrar pon_port_id basta a ONU; para olt_id precisa
        # subir cadeia pon_port -> slot -> chassis -> olt.
        stmt = (
            select(Chassis.olt_id, PonPort.pon_port_id)
            .join(PonPort, PonPort.pon_port_id == Onu.pon_port_id)
            .join(Slot, Slot.slot_id == PonPort.slot_id)
            .join(Chassis, Chassis.chassis_id == Slot.chassis_id)
            .where(Onu.onu_id == onu_id)
        )
        row = (await self._session.execute(stmt)).first()
        if row is None:
            # Defesa em profundidade: não deveria acontecer (get_by_id já
            # filtrou onu viva), mas se acontecer, levanta 404 mesmo.
            raise OnuNotFound(onu_id)
        olt_id, pon_port_id = row

        policies = await self._policy_repo.list_active_for_chain(
            onu_id=onu_id,
            pon_port_id=pon_port_id,
            olt_id=olt_id,
        )
        thresholds = resolve_policies_for_onu(policies)
        return EffectiveThresholdsRead(onu_id=onu_id, thresholds=thresholds)
