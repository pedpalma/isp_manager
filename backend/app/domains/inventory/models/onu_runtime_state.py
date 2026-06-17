# Model ORM da tabela `onu_runtime_state`.

# Estado operacional atual da ONU.
# A linha é criada AUTOMATICAMENTE pela trigger `trg_onu_runtime_state_create`
# (AFTER INSERT ON onu, com ON CONFLICT DO NOTHING). O service de ONU NUNCA
# insere aqui: conta com a trigger e lê o estado num SELECT posterior.

# Este model existe para LEITURA (embutido no detalhe da ONU). Sem CRUD próprio:
# a mutação deste estado e responsabilidade da Coleta.

# Particularidades frente ao gabarito:
# - NÃO usa TimestampMixin: a tabela tem `updated_at` mas NÃO tem `created_at`.
# - NÃO esta na lista do trigger `set_updated_at`; a Coleta seta `updated_at` explicitamente quando atualiza.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Numeric, Text, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domains.inventory.enums import ConnectionStatus, SyncStatus


class OnuRuntimeState(Base):
    """Estado operacional atual da ONU."""

    __tablename__ = "onu_runtime_state"

    # PK = FK para onu. ON DELETE CASCADE: hard delete da ONU remove o estado.
    onu_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("onu.onu_id", ondelete="CASCADE"),
        primary_key=True,
    )

    connection_status: Mapped[ConnectionStatus] = mapped_column(
        postgresql.ENUM(
            ConnectionStatus,
            name="connection_status_enum",
            create_type=False,
            values_callable=lambda e: [v.value for v in e],
        ),
        nullable=False,
        server_default=text("'unknown'"),
    )

    oper_state: Mapped[str | None] = mapped_column(Text, nullable=True)

    sync_status: Mapped[SyncStatus] = mapped_column(
        postgresql.ENUM(
            SyncStatus,
            name="sync_status_enum",
            create_type=False,
            values_callable=lambda e: [v.value for v in e],
        ),
        nullable=False,
        server_default=text("'pending'"),
    )

    last_signal_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    last_down_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # asdecimal=False -> Python float (serializa como um número no JSON).
    distance_m: Mapped[float | None] = mapped_column(
        Numeric(10, 2, asdecimal=False),
        nullable=True,
    )

    last_collected_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )

    updated_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    def __repr__(self) -> str:
        return (
            f"<OnuRuntimeState onu_id={self.onu_id} "
            f"connection_status={self.connection_status} "
            f"sync_status={self.sync_status}>"
        )
