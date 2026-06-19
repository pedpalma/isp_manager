# Model ORM da tabela `app_user_session`.

# ATENÇÃO: esta tabela NÃO tem created_at nem updated_at.
# Ela NÃO está na lista do trigger set_updated_at do DDL.
# Portanto NÃO leva TimestampMixin. Tem ciclo de vida próprio:
# issued_at, expires_at, revoked_at, last_used_at.

# Diferença para o satélite anterior: aqui quem escreve é o SERVICE (login
# cria, refresh atualiza, logout revoga), não um trigger.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import InetStr


class AppUserSession(Base):
    """Sessão de usuário (anexa um par access/refresh a uma linha rastreável).
    Permite revogar tokens (logout), listar dispositivos e auditar logins."""

    __tablename__ = "app_user_session"

    app_user_session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    app_user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("app_user.app_user_id", ondelete="CASCADE"),
        nullable=False,
    )

    # Digest sha256 do access token corrente (UNIQUE no DDL). Rotaciona no refresh.
    # É armazenado em digest, nunca o token cru.
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_hash: Mapped[str | None] = mapped_column(Text, nullable=True)

    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    # INET reutiliza o InetStr centralizado (round-trip str <-> INET).
    ip_address: Mapped[str | None] = mapped_column(InetStr, nullable=True)

    # issued_at tem DEFAULT NOW() no DDL e o app NÃO envia:
    # server_default obrigatório.
    issued_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    # expires_at é NOT NULL sem default: o service SEMPRE calcula e envia.
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<AppUserSession id={self.app_user_session_id} revoked={self.revoked_at is not None}>"
        )
