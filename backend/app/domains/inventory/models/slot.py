# Model ORM da tabela `slot`.

# Unicidade (chassis_id, slot_index) vive no DDL (uq_slot_chassis_index).
# `status` tem DEFAULT 'unknown' no DDL: a aplicação NÃO envia no INSERT,
# por isso server_default explícito no model.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, Text, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin
from app.domains.inventory.enums import PortStatus


class Slot(Base, TimestampMixin):
    """Slot dentro do chassis. Hospeda placas que expõem portas PON."""

    __tablename__ = "slot"

    slot_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    chassis_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("chassis.chassis_id"),
        nullable=False,
    )
    slot_index: Mapped[int] = mapped_column(Integer, nullable=False)
    board_type: Mapped[str | None] = mapped_column(Text, nullable=True)

    # App NÃO envia no INSERT: server_default + RETURNING garante populate em memória.
    status: Mapped[PortStatus] = mapped_column(
        postgresql.ENUM(
            PortStatus,
            name="port_status_enum",
            create_type=False,
            values_callable=lambda e: [v.value for v in e],
        ),
        nullable=False,
        server_default=text("'unknown'"),
    )

    discovered_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )

    last_seen_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<Slot chassis_id={self.chassis_id} index={self.slot_index} status={self.status}>"
