# Model ORM de optical_reading
# *Tabela PARTICIONADA por collected_at.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Numeric, PrimaryKeyConstraint, Text, func, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OpticalReading(Base):
    __tablename__ = "optical_reading"

    optical_reading_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    onu_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("onu.onu_id"),
        nullable=False,
    )

    rx_power_dbm: Mapped[float | None] = mapped_column(
        Numeric(6, 2, asdecimal=False),
        nullable=True,
    )
    tx_power_dbm: Mapped[float | None] = mapped_column(
        Numeric(6, 2, asdecimal=False),
        nullable=True,
    )
    status: Mapped[str | None] = mapped_column(Text, nullable=True)

    # alert_critical é a flag gravada pelo worker
    # quando qualquer threshold critical for violado
    alert_critical: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )

    distance_m: Mapped[float | None] = mapped_column(
        Numeric(10, 2, asdecimal=False),
        nullable=True,
    )
    temperature: Mapped[float | None] = mapped_column(
        Numeric(5, 2, asdecimal=False),
        nullable=True,
    )
    voltage: Mapped[float | None] = mapped_column(
        Numeric(6, 3, asdecimal=False),
        nullable=True,
    )
    bias_current: Mapped[float | None] = mapped_column(
        Numeric(7, 3, asdecimal=False),
        nullable=True,
    )
    collected_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    collection_source: Mapped[str | None] = mapped_column(Text, nullable=True)

    # PK composta
    __table_args__ = (
        PrimaryKeyConstraint(
            "optical_reading_id",
            "collected_at",
            name="pk_optical_reading",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<OpticalReading id={self.optical_reading_id} "
            f"onu={self.onu_id} rx={self.rx_power_dbm} tx={self.tx_power_dbm} "
            f"at={self.collected_at}>"
        )
