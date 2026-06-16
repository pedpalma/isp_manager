# Model ORM da tabela vlan.

# Unicidade (olt_id, vlan_number) TOTAL no DDL (uq_vlan_olt_number), sem
# filtro de active: desativar NAO libera o numero.
# CHECK (vlan_number BETWEEN 1 AND 4094) no banco, espelhado no schema.
# Sem deleted_at: "estar vivo" e herdado da OLT pai via JOIN no repository
# Sem relationship() (YAGNI).

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin


class Vlan(Base, TimestampMixin):
    __tablename__ = "vlan"

    vlan_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    olt_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("olt.olt_id"),
        nullable=False,
    )
    vlan_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    type: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )

    def __repr__(self) -> str:
        return f"<Vlan olt_id={self.olt_id} number={self.vlan_number}>"
