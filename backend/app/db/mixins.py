# Mixins reutilizáveis para os models ORM.

# Espelham as colunas que se repetem em quase toda tabela do DDL.sql:
#   - created_at / updated_at  -> TimestampMixin
#   - deleted_at (soft delete) -> SoftDeleteMixin

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """Adiciona created_at e updated_at (TIMESTAMPTZ, default NOW() no banco)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        # Sem onupdate: o trigger set_updated_at do Postgres cuida disso.
    )


class SoftDeleteMixin:
    """Adiciona deleted_at. NULL = registro ativo; preenchido = desativado.
    O padrão de unicidade parcial (WHERE deleted_at IS NULL) já está no DDL."""

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
