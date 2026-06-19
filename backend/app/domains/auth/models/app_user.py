# Model ORM da tabela `app_user`.
# Arquétipo catalog com DUAS unicidades TOTAIS (username, email) e campo
# sensível (password_hash, que NUNCA vai ao Read). Sem deleted_at: pausa
# administrativa via `active`, não há soft delete.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin


class AppUser(Base, TimestampMixin):
    """Usuário do sistema. FK para user_group com ON DELETE RESTRICT
    (não se apaga um grupo que ainda tem usuários)."""

    __tablename__ = "app_user"

    user_group_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("user_group.user_group_id", ondelete="RESTRICT"),
        nullable=False,
    )

    username: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False)

    # Hash argon2. Campo sensível: nunca espelhado em nenhum schema Read.
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)

    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Reset por e-mail esta FORA do V1 (sem serviço de e-mail). As colunas
    # existem no DDL e sao mapeadas, porem nenhum fluxo as preenche ainda.
    # Também sao sensíveis: nao aparecem no Read.
    reset_password_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    reset_password_expires_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    last_login_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    # created_at e updated_at vem do TimestampMixin.

    def __repr__(self) -> str:
        return f"<AppUser username={self.username!r} active={self.active}>"
