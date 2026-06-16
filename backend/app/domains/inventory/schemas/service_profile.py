# Schemas Pydantic do recurso Service Profile.

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ServiceProfileCreate(BaseModel):
    olt_id: UUID
    name: str = Field(min_length=1, max_length=255)
    version: str = Field(default="1", min_length=1, max_length=32)
    logical_name: str | None = Field(
        default=None,
        max_length=255,
        description="Nome logico do perfil replicado em N OLTs.",
    )
    raw_config: dict[str, Any] | None = None
    active: bool = Field(default=True)


class ServiceProfileUpdate(BaseModel):
    """PATCH. olt_id, name e version sao imutáveis (D13.7); fora daqui."""

    logical_name: str | None = Field(default=None, max_length=255)
    raw_config: dict[str, Any] | None = None
    active: bool | None = None


class ServiceProfileRead(BaseModel):
    service_profile_id: UUID
    olt_id: UUID
    logical_name: str | None
    name: str
    version: str
    raw_config: dict[str, Any] | None
    active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
