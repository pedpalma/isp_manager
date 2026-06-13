# Schema agregado: árvore chassis -> slots -> pon_ports de uma OLT.

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domains.inventory.enums import PonType, PortStatus


class PonPortInTopology(BaseModel):
    pon_port_id: UUID
    pon_index: int
    pon_type: PonType
    status: PortStatus

    model_config = ConfigDict(from_attributes=True)


class SlotInTopology(BaseModel):
    slot_id: UUID
    slot_index: int
    board_type: str | None
    status: PortStatus
    pon_ports: list[PonPortInTopology]

    model_config = ConfigDict(from_attributes=True)


class ChassisInTopology(BaseModel):
    chassis_id: UUID
    chassis_index: int
    description: str | None
    slots: list[SlotInTopology]

    model_config = ConfigDict(from_attributes=True)


class OltTopology(BaseModel):
    olt_id: UUID
    name: str
    chassis: list[ChassisInTopology]
