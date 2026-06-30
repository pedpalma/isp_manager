# Schemas Pydantic de normalized_command.

# Create: chave única + command_type + template_string. Imutáveis após criação.

# Update: apenas campos mutáveis. Todos opcionais.

# Read: reflete a tabela inteira.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domains.provisioning.enums import NormalizedCommandType


class NormalizedCommandBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class NormalizedCommandCreate(NormalizedCommandBase):
    """Payload de POST /normalized-commands."""

    manufacturer_id: UUID
    olt_model_id: UUID | None = None
    command_key: str = Field(min_length=1, max_length=64)
    command_type: NormalizedCommandType
    template_string: str = Field(min_length=1)
    output_parser: str | None = Field(default=None, max_length=128)
    version_constraint: str | None = Field(default=None, max_length=128)
    timeout_ms: int = Field(default=10_000, ge=100, le=600_000)
    requires_privileged: bool = False
    supports_ssh: bool = True
    supports_telnet: bool = False
    active: bool = True


class NormalizedCommandUpdate(NormalizedCommandBase):
    """Payload de PATCH /normalized-commands/{id}."""

    active: bool | None = None
    command_type: NormalizedCommandType | None = None
    template_string: str | None = Field(default=None, min_length=1)
    output_parser: str | None = Field(default=None, max_length=128)
    timeout_ms: int | None = Field(default=None, ge=100, le=600_000)
    requires_privileged: bool | None = None
    supports_ssh: bool | None = None
    supports_telnet: bool | None = None


class NormalizedCommandRead(NormalizedCommandBase):
    normalized_command_id: UUID
    manufacturer_id: UUID
    olt_model_id: UUID | None
    command_key: str
    command_type: str
    template_string: str
    output_parser: str | None
    version_constraint: str | None
    timeout_ms: int
    requires_privileged: bool
    supports_ssh: bool
    supports_telnet: bool
    active: bool
    created_at: datetime
    updated_at: datetime
