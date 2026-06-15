# Model ORM da tabela `line_profile`.

# Unicidade (olt_id, name, version) TOTAL no DDL. Versionamento: mudar de perfil cria nova `version`,
# nao se edita name/version. Sem deleted_at: ciclo herdado da OLT pai via JOIN. Sem relationship().

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin


class LineProfile(Base, TimestampMixin):
    __tablename__ = "line_profile"

    line_profile_id: Mapped[UUID] = mapped_column(
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
    upstream_bandwidth: Mapped[str] = mapped_column(Text, nullable=False)
    downstream_bandwidth: Mapped[str] = mapped_column(Text, nullable=False)
    raw_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )

    def __repr__(self) -> str:
        return f"<LineProfile olt_id={self.olt_id} name={self.name} v={self.version}>"
