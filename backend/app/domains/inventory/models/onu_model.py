# Model ORM da tabela `onu_model`.
#
# Cataloga modelos de ONU por fabricante. Carrega o `vendor_id` (ex.: 4 chars
# hex do GPON) que é usado pela rotina de descoberta para casar uma ONU
# detectada com seu modelo.

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin


class OnuModel(Base, TimestampMixin):
    """Modelo de ONU/ONT de um fabricante. Ex.: 'AN5506-04-F1', 'F660'."""

    __tablename__ = "onu_model"

    # `server_default=text("gen_random_uuid()")`: ver justificativa em
    # manufacturer.py. Sem isso, o INSERT envia NULL e viola NOT NULL da PK.
    onu_model_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    manufacturer_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("manufacturer.manufacturer_id"),
        nullable=False,
    )
    model: Mapped[str] = mapped_column(Text, nullable=False)

    # vendor_id do GPON (4 chars hex tipicamente). Opcional: nem todo modelo
    # tem ou conhecemos. Quando preenchido, é único por fabricante (constraint
    # parcial no banco: uq_onu_model_vendor_id WHERE vendor_id IS NOT NULL).
    vendor_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Categoria livre (ex.: "residencial", "empresarial", "ont_wifi"). Texto
    # simples por enquanto: virar enum só faz sentido quando a lista estabilizar.
    category: Mapped[str | None] = mapped_column(Text, nullable=True)

    # JSONB de capacidades. Estrutura flexível: {"wifi": true, "fxs": 2, ...}.
    # O domínio que consome decide o shape; aqui é apenas storage.
    capabilities_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        # Reflete `uq_onu_model` do DDL.
        UniqueConstraint("manufacturer_id", "model", name="uq_onu_model"),
        # uq_onu_model_vendor_id é UNICIDADE PARCIAL (WHERE vendor_id IS NOT NULL).
        # SQLAlchemy não tem como expressar isso em UniqueConstraint puro,
        # então não declaramos aqui: o banco já impõe. Os repositórios
        # tratam o IntegrityError correspondente.
    )

    def __repr__(self) -> str:
        return f"<OnuModel model={self.model!r} vendor_id={self.vendor_id!r}>"
