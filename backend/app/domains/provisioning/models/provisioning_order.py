# Model ORM de provisioning_order.

# Ordem persistida de uma solicitação de provisionamento. Nasce em
# 'pending' via POST /provisioning-orders, passa por 'validating'
# e 'running' no worker, e termina em success | failed | rolled_back |
# partial.

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domains.provisioning.enums import ProvisioningStatus


class ProvisioningOrder(Base):
    __tablename__ = "provisioning_order"

    provisioning_order_id: Mapped[UUID] = mapped_column(
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
    onu_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("onu.onu_id"),
        nullable=True,
    )
    app_user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("app_user.app_user_id"),
        nullable=False,
    )
    provisioning_template_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("provisioning_template.provisioning_template_id"),
        nullable=False,
    )
    retry_of_order_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("provisioning_order.provisioning_order_id"),
        nullable=True,
    )

    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[ProvisioningStatus] = mapped_column(
        PG_ENUM(
            ProvisioningStatus,
            name="provisioning_status_enum",
            create_type=False,
            values_callable=lambda e: [v.value for v in e],
        ),
        nullable=False,
        server_default=text("'pending'"),
    )

    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    snapshot_params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    requested_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
    started_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
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
            f"<ProvisioningOrder id={self.provisioning_order_id} "
            f"olt_id={self.olt_id} status={self.status}>"
        )
