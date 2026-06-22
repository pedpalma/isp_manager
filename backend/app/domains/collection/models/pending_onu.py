# Modelo ORM de pending_onu.

# Tem created_at + updated_at + trigger set_updated_at no DDL. Aplica TimestampMixin.
# NÃO tem deleted_at: o ciclo de vida é detected -> waiting -> resolved,

# A unicidade é TOTAL (sem WHERE) e é a ancora do upsert no worker.
# NÃO declarada no model: o banco enforce.

# TODO: implementar ciclo de resolução em linked_onu_id, resolution_type e resolved_at.

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin
from app.domains.collection.enums import PendingOnuState, ResolutionType


class PendingOnu(Base, TimestampMixin):
    __tablename__ = "pending_onu"

    pending_onu_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    olt_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("olt.olt_id"),
        nullable=False,
    )
    pon_port_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("pon_port.pon_port_id"),
        nullable=False,
    )
    onu_model_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("onu_model.onu_model_id"),
        nullable=True,
    )
    linked_onu_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("onu.onu_id"),
        nullable=True,
    )
    serial: Mapped[str] = mapped_column(Text, nullable=False)
    vendor_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    pon_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    state: Mapped[PendingOnuState] = mapped_column(
        PG_ENUM(
            PendingOnuState,
            name="pending_onu_state_enum",
            create_type=False,
            values_callable=lambda e: [v.value for v in e],
        ),
        server_default=text("'detected'"),
        nullable=False,
    )
    is_duplicate: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("false"),
        nullable=False,
    )
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    discovery_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_type: Mapped[ResolutionType | None] = mapped_column(
        PG_ENUM(
            ResolutionType,
            name="resolution_type_enum",
            create_type=False,
            values_callable=lambda e: [v.value for v in e],
        ),
        nullable=True,
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)

    def __repr__(self) -> str:
        return f"<PendingOnu id={self.pending_onu_id} serial={self.serial} state={self.state}>"
