# Model ORM da tabela `pon_port`.

# Unicidade (slot_id, pon_index) vive no DDL (uq_pon_port_slot_index).
# `status` tem DEFAULT no DDL e a app não envia -> server_default no model.
# `pon_type` tem DEFAULT no DDL, mas a app SEMPRE envia (schema tem default GPON)
# -> `default` no ORM basta, server_default é apenas robustez extra.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin
from app.domains.inventory.enums import PonType, PortStatus


class PonPort(Base, TimestampMixin):
    """Porta PON dentro de um slot. Ponto físico onde ONUs se conectam."""

    __tablename__ = "pon_port"

    pon_port_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    slot_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("slot.slot_id"),
        nullable=False,
    )

    pon_index: Mapped[int] = mapped_column(Integer, nullable=False)

    pon_type: Mapped[PonType] = mapped_column(
        postgresql.ENUM(
            PonType,
            name="pon_type_enum",
            create_type=False,
            values_callable=lambda e: [v.value for v in e],
        ),
        nullable=False,
        default=PonType.GPON,
    )

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
        return (
            f"<PonPort slot_id={self.slot_id} index={self.pon_index} "
            f"type={self.pon_type} status={self.status}>"
        )
