# Schemas Pydantic v2 de OltCommandProfile

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domains.inventory.enums import AccessProtocol

_FIRMWARE_MIN = 1
_FIRMWARE_MAX = 100
_VERSION_CONSTRAINT_MAX = 100
_PARSER_PROFILE_MAX = 100


class OltCommandProfileCreate(BaseModel):
    """Payload de POST via /api/v1/olt-command-profiles."""

    model_config = ConfigDict(extra="forbid")

    olt_model_id: UUID = Field(
        description="OLT model do catálogo. Precisa existir e estar ativo.",
    )

    firmware_version: UUID = Field(
        min_length=_FIRMWARE_MIN,
        max_length=_FIRMWARE_MAX,
        description="Versão de firmware. Rótulo livre.",
    )
    access_protocol: AccessProtocol = Field(
        default=AccessProtocol.SSH,
        description="Protocolo de acesso deste perfil.",
    )
    version_constraint: str | None = Field(
        default=None,
        max_length=_VERSION_CONSTRAINT_MAX,
        description="Regra semântica de versão.",
    )
    parser_profile: str | None = Field(
        default=None,
        max_length=_PARSER_PROFILE_MAX,
        description="Identificador do conjunto de parsers dessa combinação.",
    )
    active: bool = Field(
        default=True,
        description="Ativo no catálogo.",
    )

    @field_validator("firmware_version", mode="before")
    @classmethod
    def _strip_firmware(cls, v: object) -> object:
        return v.strip() if isinstance(v, str) else v

    @field_validator("version_constraint", "parser_profile", mode="before")
    @classmethod
    def _strip_optional(cls, v: object) -> object:
        if isinstance(v, str):
            stripped = v.strip()
            return stripped or None
        return v


class OltCommandProfileUpdate(BaseModel):
    """PATCH. Campos da chave única ficam de fora por serem imutáveis."""

    model_config = ConfigDict(extra="forbid")

    version_constraint: str | None = Field(
        default=None,
        max_length=_VERSION_CONSTRAINT_MAX,
    )
    parser_profile: str | None = Field(
        default=None,
        max_length=_PARSER_PROFILE_MAX,
    )
    active: bool | None = Field(default=None)

    @field_validator("version_constraint", "parser_profile", mode="before")
    @classmethod
    def _strip_optional(cls, v: object) -> object:
        if isinstance(v, str):
            stripped = v.strip()
            return stripped or None
        return v


class OltCommandProfileRead(BaseModel):
    """Leitura do catálogo"""

    model_config = ConfigDict(from_attributes=True)

    olt_command_profile_id: UUID
    olt_model_id: UUID
    firmware_version: str
    access_protocol: AccessProtocol
    version_constraint: str | None
    parser_profile: str | None
    active: bool
    created_at: datetime
    updated_at: datetime
