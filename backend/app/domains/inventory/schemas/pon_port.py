# Schemas Pydantic do recurso PonPort.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domains.inventory.enums import PonType, PortStatus


class PonPortCreate(BaseModel):
    slot_id: UUID
    pon_index: int = Field(ge=0, le=255)
    pon_type: PonType = PonType.GPON
    # status NÃO entra: DEFAULT do banco ('unknown') assume.


class PonPortUpdate(BaseModel):
    """PATCH. slot_id e pon_index são imutáveis.
    status só admite 'disabled' e 'unknown', validação no service."""

    pon_type: PonType | None = None
    status: PortStatus | None = None


class PonPortRead(BaseModel):
    pon_port_id: UUID
    slot_id: UUID
    pon_index: int
    pon_type: PonType
    status: PortStatus
    discovered_at: datetime | None
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
