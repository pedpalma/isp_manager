# Schemas Pydantic do recurso VLAN.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class VlanCreate(BaseModel):
    olt_id: UUID
    vlan_number: int = Field(ge=1, le=4094, description="ID 802.1Q (1..4094).")
    name: str | None = Field(default=None, max_length=255)
    type: str | None = Field(
        default=None,
        max_length=64,
        description="Rotulo livre (ex.: 'data', 'voip', 'mgmt').",
    )
    description: str | None = Field(default=None, max_length=255)
    active: bool = Field(default=True)


class VlanUpdate(BaseModel):
    """PATCH. olt_id e vlan_number sao imutáveis; fora daqui."""

    name: str | None = Field(default=None, max_length=255)
    type: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=255)
    active: bool | None = None


class VlanRead(BaseModel):
    vlan_id: UUID
    olt_id: UUID
    vlan_number: int
    name: str | None
    type: str | None
    description: str | None
    active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
