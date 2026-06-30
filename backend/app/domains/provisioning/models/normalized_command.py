# Model ORM da tabela `normalized_command`.

# Pausar (active=FALSE) LIBERA a chave: serve para versionar comandos
# (deixa o antigo inativo, cria o novo ativo). Re-ativar exige unicidade.

# Campos imutáveis após criação:
#   manufacturer_id, olt_model_id, command_key, version_constraint.

# Campos mutáveis:
#   active, command_type, template_string, output_parser, timeout_ms,
#   requires_privileged, supports_ssh, supports_telnet.

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin


class NormalizedCommand(Base, TimestampMixin):
    __tablename__ = "normalized_command"

    normalized_command_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

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

    command_key: Mapped[str] = mapped_column(Text, nullable=False)
    command_type: Mapped[str] = mapped_column(Text, nullable=False)
    template_string: Mapped[str] = mapped_column(Text, nullable=False)
    output_parser: Mapped[str | None] = mapped_column(Text, nullable=True)
    version_constraint: Mapped[str | None] = mapped_column(Text, nullable=True)

    timeout_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("10000"),
    )
    requires_privileged: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    supports_ssh: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    supports_telnet: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )

    def __repr__(self) -> str:
        return (
            f"<NormalizedCommand manufacturer_id{self.manufacturer_id} "
            f"olt_model_id={self.olt_model_id} command_key={self.command_key} "
            f"active={self.active}>"
        )
