# Schemas Pydantic v2 do OnuModel.

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OnuModelBase(BaseModel):
    manufacturer_id: UUID = Field(description="FK para Manufacturer.manufacturer_id.")
    model: str = Field(
        min_length=1,
        max_length=200,
        description="Nome do modelo. Ex.: 'AN5506-04-F1', 'F660'.",
    )
    vendor_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description=(
            "Identificador GPON do vendor (geralmente 4 chars hex). "
            "Usado pela descoberta para casar uma ONU detectada com o modelo."
        ),
    )
    category: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Categoria livre, ex.: 'residencial', 'empresarial', 'ont_wifi'.",
    )
    capabilities_json: dict[str, Any] | None = Field(
        default=None,
        description=(
            'Capacidades em formato livre. Ex.: `{"wifi": true, "fxs": 2, "catv": false}`.'
        ),
    )
    active: bool = Field(default=True)


class OnuModelCreate(OnuModelBase):
    """Corpo do POST /onu-models."""


class OnuModelUpdate(BaseModel):
    """Corpo do PATCH /onu-models/{id}.

    `manufacturer_id` não é atualizável (mesma justificativa de OltModel).
    """

    model: str | None = Field(default=None, min_length=1, max_length=200)
    vendor_id: str | None = Field(default=None, min_length=1, max_length=64)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    capabilities_json: dict[str, Any] | None = None
    active: bool | None = None


class OnuModelRead(OnuModelBase):
    model_config = ConfigDict(from_attributes=True)

    onu_model_id: UUID
    created_at: datetime
    updated_at: datetime
