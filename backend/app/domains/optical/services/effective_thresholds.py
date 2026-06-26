# Service de diagnóstico de thresholds efetivos por ONU.
# Resolve hierarquia (onu > pon_port > olt > global) em UMA query
# (list_active_for_chain) e devolve dict cobrindo TODAS as métricas
# suportadas. None significa "sem política aplicável".
# NÃO usa o ThresholdCache: este é endpoint de inspeção do operador,
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

        # Sobe cadeia onu -> pon_port -> slot -> chassis -> olt_id.
        # CORREÇÃO M17: select_from(Onu) explícito é obrigatório.
        # Sem ele, SQLAlchemy não identifica a tabela âncora e gera SQL
        # com FROM duplo (UndefinedTableError em runtime). A coluna
        # Onu.onu_id no WHERE não é suficiente para inferir âncora quando
        # o SELECT só projeta colunas de outras tabelas.
        stmt = (
            select(Chassis.olt_id, PonPort.pon_port_id)
            .select_from(Onu)
            .join(PonPort, PonPort.pon_port_id == Onu.pon_port_id)
            .join(Slot, Slot.slot_id == PonPort.slot_id)
            .join(Chassis, Chassis.chassis_id == Slot.chassis_id)
            .where(Onu.onu_id == onu_id)
        )
        row = (await self._session.execute(stmt)).first()
        if row is None:
            # Defesa em profundidade: get_by_id já filtrou ONU viva, mas
            # se a cadeia estiver quebrada (ex: PON deletada de forma
            # inválida), respondemos 404 também.
            raise OnuNotFound(onu_id)
        olt_id, pon_port_id = row

        policies = await self._policy_repo.list_active_for_chain(
            onu_id=onu_id,
            pon_port_id=pon_port_id,
            olt_id=olt_id,
        )
        thresholds = resolve_policies_for_onu(policies)
        return EffectiveThresholdsRead(onu_id=onu_id, thresholds=thresholds)
