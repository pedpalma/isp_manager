# Schemas Pydantic V2 de ProvisioningOrder

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domains.provisioning.enums import RollbackStatus


class ProvisioningRollBackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provisioning_rollback_id: UUID
    provisioning_order_id: UUID
    reason: str
    rollback_commands: list[dict[str, Any]]
    rollback_status: RollbackStatus
    output_received: str | None
    executed: bool
    executed_at: datetime | None
    created_at: datetime
