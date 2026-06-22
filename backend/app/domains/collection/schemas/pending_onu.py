# Schema Pydantic v2 de PendingOnu.

# O cliente não cria nem altera pending_onu via API:
# a tabela é populada pelo worker via upsert, executando o ciclo de descoberta.

# Resolução (state -> waiting/resolved + resolution_type + linked_onu_id)


from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domains.collection.enums import PendingOnuState, ResolutionType


class PendingOnuRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pending_onu_id: UUID
    olt_id: UUID
    pon_port_id: UUID
    onu_model_id: UUID | None
    linked_onu_id: UUID | None
    serial: str
    vendor_id: str | None
    pon_position: int | None
    state: PendingOnuState
    is_duplicate: bool
    raw_payload: dict[str, Any] | None
    discovery_source: str | None
    resolution_type: ResolutionType | None
    first_seen_at: datetime
    last_seen_at: datetime
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime
