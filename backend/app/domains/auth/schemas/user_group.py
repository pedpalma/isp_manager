# Schemas Pydantic v2 do UserGroup

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UserGroupCreate(BaseModel):
    """Corpo do POST /user-groups."""

    name: str = Field(min_length=1, max_length=100)
    permissions_json: dict[str, Any] = Field(
        default_factory=dict,
        description="Permissões do grupo.",
    )
    active: bool = Field(default=True)


class UserGroupUpdate(BaseModel):
    """Corpo do PATCH /user-groups/{id}. Semântica PATCH.
    `name` é imutável: não entra aqui."""

    permissions_json: dict[str, Any] | None = None
    active: bool | None = None


class UserGroupRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_group_id: UUID
    name: str
    permissions_json: dict[str, Any]
    active: bool
    created_at: datetime
    updated_at: datetime
