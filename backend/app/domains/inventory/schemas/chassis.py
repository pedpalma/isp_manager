# Schemas Pydantic do recurso Chassis.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChassisCreate(BaseModel):
    olt_id: UUID
    chassis_index: int = Field(ge=0, le=255)
    description: str | None = Field(default=None, max_length=255)


class ChassisUpdate(BaseModel):
    """PATCH. olt_id e chassis_index são imutáveis (D12.6); não aparecem aqui.
    `description` opcional e nullable (pode limpar com null explicito)."""

    description: str | None = Field(default=None, max_length=255)


class ChassisRead(BaseModel):
    chassis_id: UUID
    olt_id: UUID
    chassis_index: int
    description: str | None
    discovered_at: datetime | None
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
