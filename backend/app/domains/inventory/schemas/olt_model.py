# Schemas Pydantic v2 do OltModel.
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OltModelBase(BaseModel):
    manufacturer_id: UUID = Field(description="FK para Manufacturer.manufacturer_id.")
    model: str = Field(
        min_length=1,
        max_length=200,
        description="Nome do modelo, conforme o fabricante. Ex.: 'AN5516-04', 'C320'.",
    )
    active: bool = Field(default=True)


class OltModelCreate(OltModelBase):
    """Corpo do POST /olt-models."""


class OltModelUpdate(BaseModel):
    """Corpo do PATCH /olt-models/{id}.

    `manufacturer_id` NÃO é atualizável: trocar o fabricante de um modelo
    existente leva a inconsistências (OLTs já cadastradas apontariam para
    um modelo de fabricante diferente). Se realmente for o caso, o caminho
    correto é desativar e criar outro.
    """

    model: str | None = Field(default=None, min_length=1, max_length=200)
    active: bool | None = None


class OltModelRead(OltModelBase):
    model_config = ConfigDict(from_attributes=True)

    olt_model: UUID
    created_at: datetime
    updated_at: datetime
