# Modelo ORM de collection_log.

# Tabela sé tem executed_at, sem created_at/updated_at.
# NÃO aplicar TimestampMixin.

# Cada linha é um step de comando dentro de um collection_job.
# Relação 1:N. Embed no detalhe segue padrão do TopologyService, NÃO o padrão 1:1.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CollectionLog(Base):
    __tablename__ = "collection_log"

    collection_log_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    collection_job_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("collection_job.collection_job_id"),
        nullable=False,
    )
    olt_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("olt.olt_id"),
        nullable=False,
    )
    step_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    command_sent: Mapped[str] = mapped_column(Text, nullable=False)
    output_received: Mapped[str | None] = mapped_column(Text, nullable=True)
    parser_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    success: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("false"),
        nullable=False,
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    executed_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<CollectionLog id={self.collection_log_id} "
            f"job={self.collection_job_id} step={self.step_name} success={self.success}>"
        )
