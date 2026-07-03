# Schema Pydantic de ProvisioningStep

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProvisioningStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provisioning_step_id: UUID
    provisioning_order_id: UUID
    step_order: int
    step_key: str
    phase: str
    command_sent: str | None
    output_received: str | None
    parser_output: dict[str, Any] | None
    success: bool
    duration_ms: int | None
    executed_at: datetime
