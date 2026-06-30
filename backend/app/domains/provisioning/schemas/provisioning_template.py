# Schemas Pydantic de provisioning_template.

# Create: campos da chave única (manufacturer_id, olt_model_id, name, version)
# + template_scope + raw_template. Imutáveis após criação.

# Update: apenas campos mutáveis (active, firmware_constraint, command_vars,
# raw_template). Todos opcionais; payload vazio é no-op.

# Read: reflete a tabela. created_by_user_id, created_at, updated_at expostos.


from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domains.provisioning.enums import TemplateScope
from app.domains.provisioning.schemas.raw_template import RawTemplate


class ProvisioningTemplateBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProvisioningTemplateCreate(ProvisioningTemplateBase):
    """Payload de POST /provisioning-templates."""

    manufacturer_id: UUID
    olt_model_id: UUID | None = None
    template_scope: TemplateScope = TemplateScope.ONU_PROVISION
    name: str = Field(min_length=1, max_length=128)
    version: str = Field(default="1", min_length=1, max_length=32)

    firmware_constraint: str | None = Field(default=None, max_length=128)
    command_vars: dict[str, Any] | None = None
    raw_template: RawTemplate

    active: bool = True


class ProvisioningTemplateUpdate(ProvisioningTemplateBase):
    """Payload de PATCH /provisioning-templates/{id}."""

    active: bool | None = None
    firmware_constraint: str | None = Field(default=None, max_length=128)
    command_vars: dict[str, Any] | None = None
    raw_template: RawTemplate | None = None


class ProvisioningTemplateRead(ProvisioningTemplateBase):
    """Resposta de GET/POST/PATCH."""

    provisioning_template_id: UUID
    manufacturer_id: UUID
    olt_model_id: UUID | None
    created_by_user_id: UUID | None
    template_scope: str
    name: str
    version: str
    firmware_constraint: str | None
    command_vars: dict[str, Any] | None
    raw_template: dict[str, Any]
    active: bool
    created_at: datetime
    updated_at: datetime
