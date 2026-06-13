# Schemas Pydantic do recurso Slot.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domains.inventory.enums import PortStatus


class SlotCreate(BaseModel):
    chassis_id: UUID
    slot_index: int = Field(ge=0, le=255)
    board_type: str | None = Field(default=None, max_length=64)
    # status NÃO entra: DEFAULT do banco ('unknown') assume.


class SlotUpdate(BaseModel):
    """PATCH. chassis_id e slot_index são imutáveis.
    status só admite 'disabled' e 'unknown', validação no service."""

    board_type: str | None = Field(default=None, max_length=64)
    status: PortStatus | None = None


class SlotRead(BaseModel):
    slot_id: UUID
    chassis_id: UUID
    slot_index: int
    board_type: str | None
    status: PortStatus
    discovered_at: datetime | None
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
