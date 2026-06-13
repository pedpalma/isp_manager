# Service da Topologia: monta árvore OLT -> chassis -> slots -> pon_ports.

# Sem `relationship()` ORM (YAGNI). Faz 4 queries (uma por nível, IN clause
# para os pais), sem N+1. Agrega em Python.

from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.domains.inventory.exceptions import OltNotFound
from app.domains.inventory.models.pon_port import PonPort
from app.domains.inventory.models.slot import Slot
from app.domains.inventory.repositories.chassis import ChassisRepository
from app.domains.inventory.repositories.olt import OltRepository
from app.domains.inventory.repositories.pon_port import PonPortRepository
from app.domains.inventory.repositories.slot import SlotRepository
from app.domains.inventory.schemas.topology import (
    ChassisInTopology,
    OltTopology,
    PonPortInTopology,
    SlotInTopology,
)


class TopologyService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_olt(self, olt_id: UUID, *, actor: Actor) -> OltTopology:
        del actor
        olt_repo = OltRepository(self._session)
        olt = await olt_repo.get_by_id(olt_id)
        if olt is None:
            raise OltNotFound(olt_id)

        chassis_repo = ChassisRepository(self._session)
        all_chassis = await chassis_repo.list_all_for_olt(olt_id)

        if not all_chassis:
            return OltTopology(olt_id=olt.olt_id, name=olt.name, chassis=[])

        chassis_ids = [c.chassis_id for c in all_chassis]
        slot_repo = SlotRepository(self._session)
        all_slots = await slot_repo.list_all_for_chassis_ids(chassis_ids)

        all_pons: list[PonPort] = []
        if all_slots:
            slot_ids = [s.slot_id for s in all_slots]
            pon_repo = PonPortRepository(self._session)
            all_pons = list(await pon_repo.list_all_for_slot_ids(slot_ids))

        # Agrupa em árvore.
        pons_by_slot: dict[UUID, list[PonPort]] = defaultdict(list)
        for p in all_pons:
            pons_by_slot[p.slot_id].append(p)

        slots_by_chassis: dict[UUID, list[Slot]] = defaultdict(list)
        for s in all_slots:
            slots_by_chassis[s.chassis_id].append(s)

        chassis_dtos: list[ChassisInTopology] = []
        for c in all_chassis:
            slot_dtos: list[SlotInTopology] = []
            for s in slots_by_chassis.get(c.chassis_id, []):
                pon_dtos = [
                    PonPortInTopology.model_validate(p) for p in pons_by_slot.get(s.slot_id, [])
                ]
                slot_dtos.append(
                    SlotInTopology(
                        slot_id=s.slot_id,
                        slot_index=s.slot_index,
                        board_type=s.board_type,
                        status=s.status,
                        pon_ports=pon_dtos,
                    )
                )
            chassis_dtos.append(
                ChassisInTopology(
                    chassis_id=c.chassis_id,
                    chassis_index=c.chassis_index,
                    description=c.description,
                    slots=slot_dtos,
                )
            )

        return OltTopology(
            olt_id=olt.olt_id,
            name=olt.name,
            chassis=chassis_dtos,
        )
