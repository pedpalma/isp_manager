# Schemas Pydantic do recurso Line Profile (perfil de linha / banda)

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LineProfileCreate(BaseModel):
    olt_id: UUID
    name: str = Field(min_length=1, max_length=255)
    version: str = Field(default="1", min_length=1, max_length=32)
    logical_name: str | None = Field(
        default=None,
        max_length=255,
        description="Nome logico do perfil replicado em N OLTs.",
    )
    upstream_bandwidth: str = Field(min_length=1, max_length=64)
    downstream_bandwidth: str = Field(min_length=1, max_length=64)
    raw_config: dict[str, Any] | None = None
    active: bool = Field(default=True)


class LineProfileUpdate(BaseModel):
    """PATCH. olt_id, name e version sao imutáveis; fora daqui.
    Banda e mutável in-place; enviar raw_config=null limpa o JSONB."""

    logical_name: str | None = Field(default=None, max_length=255)
    upstream_bandwidth: str | None = Field(default=None, min_length=1, max_length=64)
    downstream_bandwidth: str | None = Field(default=None, min_length=1, max_length=64)
    raw_config: dict[str, Any] | None = None
    active: bool | None = None


class LineProfileRead(BaseModel):
    line_profile_id: UUID
    olt_id: UUID
    logical_name: str | None
    name: str
    version: str
    upstream_bandwidth: str
    downstream_bandwidth: str
    raw_config: dict[str, Any] | None
    active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
