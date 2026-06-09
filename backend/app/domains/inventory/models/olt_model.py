# Model ORM da tabela `olt_model`.
#
# Mapeia o catálogo de modelos de OLT por fabricante. Sem firmware aqui
# (firmware é granularidade do `olt_command_profile`, do próximo bloco).

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin


class OltModel(Base, TimestampMixin):
    """Modelo de OLT de um fabricante. Ex.: 'AN5516-04', 'C320', 'C600'."""

    __tablename__ = "olt_model"

    # `server_default=text("gen_random_uuid()")`: ver justificativa em
    # manufacturer.py. Sem isso, o INSERT envia NULL e viola NOT NULL da PK.
    olt_model_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    manufacturer_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        # ON DELETE não declarado: o DDL não tem, então sai como RESTRICT
        # (padrão). É o comportamento desejado: não dá para apagar fabricante
        # se ainda houver modelos vinculados.
        ForeignKey("manufacturer.manufacturer_id"),
        nullable=False,
    )
    model: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        # Reflete a constraint `uq_olt_model` do DDL.sql.
        UniqueConstraint("manufacturer_id", "model", name="uq_olt_model"),
    )

    def __repr__(self) -> str:
        return f"<OltModel model={self.model!r} active={self.active}>"
