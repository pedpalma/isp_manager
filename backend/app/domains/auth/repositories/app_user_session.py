# Repository do AppUserSession.

# O método central é `get_active_principal`: resolve sessão + usuário +
# grupo em UMA query (sem relationship(), via JOIN explicito), já filtrando
# sessão não revogada, não expirada e usuário ativo. É o coração da
# verificação de revogação stateful-seletiva: só as rotas
# autenticadas pagam esta query; o inventário não à executa.

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import Row, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.models.app_user import AppUser
from app.domains.auth.models.app_user_session import AppUserSession
from app.domains.auth.models.user_group import UserGroup


class AppUserSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, sess: AppUserSession) -> None:
        self._session.add(sess)
        await self._session.flush()

    async def get_by_id(self, session_id: UUID) -> AppUserSession | None:
        stmt = select(AppUserSession).where(AppUserSession.app_user_session_id == session_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_principal(
        self, session_id: UUID
    ) -> Row[tuple[AppUserSession, AppUser, UserGroup]] | None:
        """Sessão viva + dono + grupo, em uma query. Vivo significa:
        revoked_at IS NULL, expires_at > now, app_user.active = true.
        Retorna None se qualquer condição falhar."""
        stmt = (
            select(AppUserSession, AppUser, UserGroup)
            .join(AppUser, AppUser.app_user_id == AppUserSession.app_user_id)
            .join(UserGroup, UserGroup.user_group_id == AppUser.user_group_id)
            .where(AppUserSession.app_user_session_id == session_id)
            .where(AppUserSession.revoked_at.is_(None))
            .where(AppUserSession.expires_at > func.now())
            .where(AppUser.active.is_(True))
        )
        result = await self._session.execute(stmt)
        return result.first()

    async def revoke_by_id(self, session_id: UUID) -> None:
        """Revoga uma sessão (logout). Idempotente: re-revogar não quebra."""
        stmt = (
            update(AppUserSession)
            .where(AppUserSession.app_user_session_id == session_id)
            .where(AppUserSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))  # noqa: UP017
        )
        await self._session.execute(stmt)

    async def revoke_all_for_user(self, app_user_id: UUID) -> None:
        """Revoga todas as sessões vivas do usuário. Usado na troca de senha
        para forçar novo login em todos os dispositivos."""
        stmt = (
            update(AppUserSession)
            .where(AppUserSession.app_user_id == app_user_id)
            .where(AppUserSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))  # noqa: UP017
        )
        await self._session.execute(stmt)

    async def flush(self) -> None:
        await self._session.flush()
