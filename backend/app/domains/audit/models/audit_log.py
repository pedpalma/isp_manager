# Model do audit_log.

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditLog(Base):
    """Registro imutável de uma ação sensível do sistema."""

    __tablename__ = "audit_log"

    # PK do servidor via gen_random_uuid() (DEFAULT do DDL).
    audit_log_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    # Ator (nullable: sistema/worker não tem app_user).
    app_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("app_user.app_user_id"),
        nullable=True,
    )

    # Alvos convenientes para filtros de UI (todos nullable).
    olt_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("olt.olt_id"),
        nullable=True,
    )
    onu_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("onu.onu_id"),
        nullable=True,
    )
    provisioning_order_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("provisioning_order.provisioning_order_id"),
        nullable=True,
    )

    # Alvo genérico (obrigatório).
    entity_type: Mapped[str] = mapped_column(nullable=False)
    entity_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)

    # Ação e resultado (TEXT no DDL; validação em enums.py).
    action: Mapped[str] = mapped_column(nullable=False)
    result: Mapped[str] = mapped_column(nullable=False)

    error_detail: Mapped[str | None] = mapped_column(nullable=True)

    before_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    after_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Ver docstring do módulo: coluna no DDL é `metadata`; atributo Python
    # renomeado por conflito com DeclarativeBase.metadata.
    event_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
    )

    request_id: Mapped[str | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=text("now()"),
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog id={self.audit_log_id} action={self.action} "
            f"result={self.result} entity={self.entity_type}:{self.entity_id}>"
        )
