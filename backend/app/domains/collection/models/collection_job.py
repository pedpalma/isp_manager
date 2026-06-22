# Modelo ORM de collection_job.

# IMPORTANTE: tabela tem apenas created_at (sem updated_at).
# Mesma lição de onu_runtime_state e app_user_session: NÃO aplicar TimestampMixin.
# As transições de status (pending -> running -> success/failed/partial)
# são escritas explicitamente pelo worker via UPDATE direto.

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domains.collection.enums import JobStatus, JobTriggerType


class CollectionJob(Base):
    __tablename__ = "collection_job"

    collection_job_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    olt_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("olt.olt_id"),
        nullable=False,
    )
    # requested_by_user_id é NULLABLE no SQL.
    # Auth obrigatória nas rotas de coleta, sempre virá preenchido pela request.
    # É mantido nullable=True para preservar contrato DDL.
    # TODO: permitir disparos sistêmicos no futuro.
    requested_by_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("app_user.app_user_id"),
        nullable=True,
    )
    job_type: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_type: Mapped[JobTriggerType] = mapped_column(
        PG_ENUM(
            JobTriggerType,
            name="job_trigger_type_enum",
            create_type=False,
            values_callable=lambda e: [v.value for v in e],
        ),
        server_default=text("'manual'"),
        nullable=False,
    )
    target_scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[JobStatus] = mapped_column(
        PG_ENUM(
            JobStatus,
            name="job_status_enum",
            create_type=False,
            values_callable=lambda e: [v.value for v in e],
        ),
        server_default=text("'pending'"),
        nullable=False,
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        server_default=text("0"),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<CollectionJob id={self.collection_job_id} olt={self.olt_id} "
            f"type={self.job_type} status={self.status}>"
        )
