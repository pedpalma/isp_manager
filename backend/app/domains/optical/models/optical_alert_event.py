# Model ORM de optical_alert_event

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Numeric, Text, func, text
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domains.optical.enums import OpticalAlertStatus


class OpticalAlertEvent(Base):
    __tablename__ = "optical_alert_event"

    optical_alert_event_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    onu_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("onu.onu_id"),
        nullable=False,
    )
    policy_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("optical_threshold_policy.optical_threshold_policy_id"),
        nullable=False,
    )
    metric_name: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[float] = mapped_column(
        Numeric(8, 3, asdecimal=False),
        nullable=False,
    )
    status: Mapped[OpticalAlertStatus] = mapped_column(
        PG_ENUM(
            OpticalAlertStatus,
            name="optical_alert_status_enum",
            create_type=False,
            values_callable=lambda e: [v.value for v in e],
        ),
        server_default=text("'open'"),
        nullable=False,
    )
    triggered_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<OpticalAlertEvent id={self.optical_alert_event_id} "
            f"onu={self.onu_id} metric={self.metric_name} "
            f"value={self.value} status={self.status}>"
        )
