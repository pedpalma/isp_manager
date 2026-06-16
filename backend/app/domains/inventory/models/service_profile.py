# Model ORM da tabela `service_profile`

# Mesma familia do line_profile: unicidade (olt_id, name, version) TOTAL,
# versionamento, sem deleted_at (ciclo herdado da OLT pai via JOIN).

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin


class ServiceProfile(Base, TimestampMixin):
    __tablename__ = "service_profile"

    service_profile_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    olt_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("olt.olt_id"),
        nullable=False,
    )
    logical_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'1'"),
    )
    raw_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )

    def __repr__(self) -> str:
        return f"<ServiceProfile olt_id={self.olt_id} name={self.name} v={self.version}>"
