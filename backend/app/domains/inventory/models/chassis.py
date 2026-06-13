# Model ORM da tabela `chassis`.

# Unicidade (olt_id, chassis_index) vive no DDL (uq_chassis_olt_index).
# Sem `relationship()` (YAGNI). Joins manuais nos repositories cascateiam
# para a OLT pai e respeitam o soft delete dela.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin


class Chassis(Base, TimestampMixin):
    """Chassis de uma OLT. Sem `deleted_at` no DDL: ciclo via DELETE não exposto.
    Em runtime, considera-se 'vivo' se a OLT pai está viva."""

    __tablename__ = "chassis"

    chassis_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    olt_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("olt.olt_id"),
        nullable=False,
    )
    chassis_index: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    discovered_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    # created_at / updated_at vêm do TimestampMixin.

    def __repr__(self) -> str:
        return f"<Chassis olt_id={self.olt_id} index={self.chassis_index}>"
