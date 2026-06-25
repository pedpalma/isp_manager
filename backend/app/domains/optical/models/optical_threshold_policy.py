# Model ORM de optical_threshold_policy

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, Numeric, Text, text
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin
from app.domains.optical.enums import OpticalScopeType, OpticalSeverity


class OpticalThresholdPolicy(Base, TimestampMixin):
    __tablename__ = "optical_threshold_policy"

    optical_threshold_policy_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    scope_type: Mapped[OpticalScopeType] = mapped_column(
        PG_ENUM(
            OpticalScopeType,
            name="optical_scope_type_enum",
            create_type=False,
            values_callable=lambda e: [v.value for v in e],
        ),
        nullable=False,
    )

    scope_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
    )
    metric_name: Mapped[str] = mapped_column(Text, nullable=False)
    threshold_min: Mapped[float | None] = mapped_column(
        Numeric(8, 3, asdecimal=False),
        nullable=True,
    )
    threshold_max: Mapped[float | None] = mapped_column(
        Numeric(8, 3, asdecimal=False),
        nullable=True,
    )
    severity: Mapped[OpticalSeverity] = mapped_column(
        PG_ENUM(
            OpticalSeverity,
            name="optical_severity_enum",
            create_type=False,
            values_callable=lambda e: [v.value for v in e],
        ),
        server_default=text("'warning'"),
        nullable=False,
    )
    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )

    def __repr__(self) -> str:
        return (
            f"<OpticalThresholdPolicy id={self.optical_threshold_policy_id} "
            f"scope={self.scope_type.value} metric={self.metric_name} "
            f"min={self.threshold_min} max={self.threshold_max}>"
        )
