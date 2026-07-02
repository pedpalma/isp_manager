# Model ORM de provisioning_step.


from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProvisioningStep(Base):
    __tablename__ = "provisioning_step"

    provisioning_step_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    provisioning_order_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "provisioning_order.provisioning_order_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    step_key: Mapped[str] = mapped_column(Text, nullable=False)
    phase: Mapped[str] = mapped_column(Text, nullable=False)

    command_sent: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_received: Mapped[str | None] = mapped_column(Text, nullable=True)
    parser_output: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    success: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    executed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    def __repr__(self) -> str:
        return (
            f"<ProvisioningStep order_id={self.provisioning_order_id} "
            f"step_order={self.step_order} step_key={self.step_key!r} "
            f"success={self.success}>"
        )
