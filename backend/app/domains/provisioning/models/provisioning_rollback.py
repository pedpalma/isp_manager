# Model ORM de provisioning_rollback.


from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domains.provisioning.enums import RollbackStatus


class ProvisioningRollback(Base):
    __tablename__ = "provisioning_rollback"

    provisioning_rollback_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    provisioning_order_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("provisioning_order.provisioning_order_id"),
        nullable=False,
    )

    reason: Mapped[str] = mapped_column(Text, nullable=False)
    rollback_commands: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
    )

    rollback_status: Mapped[RollbackStatus] = mapped_column(
        PG_ENUM(
            RollbackStatus,
            name="rollback_status_enum",
            create_type=False,
            values_callable=lambda e: [v.value for v in e],
        ),
        nullable=False,
        server_default=text("'pending'"),
    )

    output_received: Mapped[str | None] = mapped_column(Text, nullable=True)

    executed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    executed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    def __repr__(self) -> str:
        return (
            f"<ProvisioningRollback order_id={self.provisioning_order_id} "
            f"status={self.rollback_status} executed={self.executed}>"
        )
