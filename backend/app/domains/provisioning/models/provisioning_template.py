# Model ORM da tabela `provisioning_template`.

# Campos imutáveis após criação (não entram em Update):
#   manufacturer_id, olt_model_id, name, version, template_scope.

# Campos mutáveis:
#   active, firmware_constraint, command_vars, raw_template.

# raw_template (JSONB NOT NULL): estrutura validada pelo schema Pydantic
#   RawTemplate (vide schemas/raw_template.py).

# created_by_user_id: FK para app_user. Preenchido pelo Actor que cria via API.

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin


class ProvisioningTemplate(Base, TimestampMixin):
    __tablename__ = "provisioning_template"

    provisioning_template_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    # FKs com model existente -> ForeignKey() normal.
    manufacturer_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("manufacturer.manufacturer_id"),
        nullable=False,
    )
    olt_model_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("olt_model.olt_model_id"),
        nullable=True,
    )
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("app_user.app_user_id"),
        nullable=True,
    )

    # Server_default OBRIGATÓRIO (app pode omitir e o DDL completa).
    template_scope: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'onu_provision'"),
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'1'"),
    )

    firmware_constraint: Mapped[str | None] = mapped_column(Text, nullable=True)
    command_vars: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    raw_template: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )

    # created_at / updated_at vêm do TimestampMixin (server_default now()).

    def __repr__(self) -> str:
        return (
            f"<ProvisioningTemplate manufacturer_id={self.manufacturer_id} "
            f"olt_model_id={self.olt_model_id} name={self.name!r} version={self.version!r}>"
        )
