# Schemas Pydantic v2 do Manufacturer.
#
# Padrão Create/Update/Read:
#   - *Create*: usado no POST (corpo da requisição que cria um recurso).
#   - *Update*: usado no PATCH (todos os campos opcionais; só atualiza os
#                 presentes).
#   - *Read*:   usado no response_model (o que sai para o cliente; inclui
#                 ids e timestamps gerenciados pelo banco).

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# Regra de slug:
#   - lowercase,
#   - dígito ou letra no primeiro caractere,
#   - sem espaço (apenas letras, dígitos, `-` e `_`),
#   - até 64 caracteres.
# Ex. válidos: "huawei", "zte", "fiberhome", "nokia", "tp-link", "v-sol_b".
_SLUG_PATTERN = r"^[a-z0-9][a-z0-9_-]{0,63}$"


class ManufacturerBase(BaseModel):
    name: str = Field(min_length=1, max_length=200, description="Nome do fabricante.")
    slug: str = Field(
        min_length=1,
        max_length=64,
        pattern=_SLUG_PATTERN,
        description=(
            "Apelido curto, lowercase, sem espaços. "
            "Usado em integrações e URLs internas."
        ),
    )
    active: bool = Field(default=True, description="Se FALSE, fica oculto em listagens.")


class ManufacturerCreate(ManufacturerBase):
    """Corpo do POST /manufacturers."""


class ManufacturerUpdate(BaseModel):
    """Corpo do PATCH /manufacturers/{id}. Todos os campos opcionais.

    Só os campos PRESENTES no JSON são atualizados (semântica PATCH).
    """

    name: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(default=None, min_length=1, max_length=64, pattern=_SLUG_PATTERN)
    active: bool | None = None


class ManufacturerRead(ManufacturerBase):
    """Resposta de leitura. Inclui os campos gerados pelo banco."""

    # `from_attributes=True` permite construir o schema a partir de uma
    # instância ORM (`ManufacturerRead.model_validate(orm_obj)`).
    model_config = ConfigDict(from_attributes=True)

    manufacturer_id: UUID
    created_at: datetime
    updated_at: datetime
