# Service de autenticação (login / refresh / logout / change-password).

# Modelo de sessão: JWT stateless HS256 com verificação de revogação stateful-seletiva.
# O login cria UMA linha em app_user_session cujo PK é o `jti` dos dois tokens.
# Logout revoga a linha. Refresh exige a linha viva e o refresh_token_hash conferindo.
# As rotas autenticadas checam revogação via AppUserSessionRepository.get_active_principal;
# o inventário não paga essa query (continua em system_actor).

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.config import settings
from app.core.logging import get_logger
from app.domains.audit.enums import AuditAction, AuditResult
from app.domains.audit.services.audit_log import AuditLogService
from app.domains.auth.exceptions import (
    AppUserNotFound,
    CurrentPasswordInvalid,
    InvalidCredentials,
    InvalidToken,
)
from app.domains.auth.models.app_user_session import AppUserSession
from app.domains.auth.repositories.app_user import AppUserRepository
from app.domains.auth.repositories.app_user_session import AppUserSessionRepository
from app.domains.auth.schemas.auth import (
    AccessTokenResponse,
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
)
from app.domains.auth.security import (
    TOKEN_TYPE_REFRESH,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)

log = get_logger(__name__)


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = AppUserRepository(session)
        self._sessions = AppUserSessionRepository(session)
        self._audit = AuditLogService(session)

    def _access_ttl_seconds(self) -> int:
        return settings.security.access_token_expire_minutes * 60

    async def login(
        self,
        data: LoginRequest,
        *,
        ip_address: str | None,
        user_agent: str | None,
    ) -> TokenResponse:
        user = await self._users.get_by_username(data.username)
        # Resposta genérica: nao revela se foi username inexistente,
        # usuário inativo ou senha errada.
        if user is None or not user.active:
            raise InvalidCredentials()
        if not verify_password(user.password_hash, data.password):
            raise InvalidCredentials()

        # PK gerado em Python para amarrar os dois tokens (jti) a esta linha
        # sem ciclo (token precisa do jti; sessão precisa do token_hash).
        session_id = uuid4()
        access = create_access_token(subject=str(user.app_user_id), session_id=str(session_id))
        refresh = create_refresh_token(subject=str(user.app_user_id), session_id=str(session_id))

        now = datetime.now(timezone.utc)  # noqa: UP017
        expires_at = now + timedelta(minutes=settings.security.refresh_token_expire_minutes)
        sess = AppUserSession(
            app_user_session_id=session_id,
            app_user_id=user.app_user_id,
            token_hash=hash_token(access),
            refresh_token_hash=hash_token(refresh),
            user_agent=user_agent,
            ip_address=ip_address,
            expires_at=expires_at,
        )
        self._session.add(sess)
        user.last_login_at = now
        await self._session.flush()

        self_actor = Actor(
            actor_id=user.app_user_id,
            username=user.username,
            is_system=False,
        )
        await self._audit.record(
            actor=self_actor,
            action=AuditAction.AUTH_LOGIN,
            result=AuditResult.SUCCESS,
            entity_type="app_user",
            entity_id=user.app_user_id,
            extra={
                "session_id": str(session_id),
                "ip_address": ip_address,
                "user_agent": user_agent[:256] if user_agent else None,
            },
        )
        await self._session.commit()

        log.info(
            "auth.login",
            app_user_id=str(user.app_user_id),
            session_id=str(session_id),
            actor=user.username,
        )
        return TokenResponse(
            access_token=access,
            refresh_token=refresh,
            token_type="bearer",
            expires_in=self._access_ttl_seconds(),
            must_change_password=user.must_change_password,
        )

    async def refresh(self, data: RefreshRequest) -> AccessTokenResponse:
        try:
            payload = decode_token(data.refresh_token)
        except jwt.InvalidTokenError as exc:
            raise InvalidToken() from exc

        if payload.get("type") != TOKEN_TYPE_REFRESH:
            raise InvalidToken()
        jti = payload.get("jti")
        if not jti:
            raise InvalidToken()
        try:
            session_id = UUID(jti)
        except (ValueError, TypeError) as exc:
            raise InvalidToken() from exc

        row = await self._sessions.get_active_principal(session_id)
        if row is None:
            raise InvalidToken()
        sess, user, _group = row

        # Confere que o refresh apresentado é o mesmo que originou a sessão.
        if sess.refresh_token_hash != hash_token(data.refresh_token):
            raise InvalidToken()

        access = create_access_token(
            subject=str(user.app_user_id),
            session_id=str(sess.app_user_session_id),
        )
        # Rotaciona o token_hash (novo access) e marca uso. Refresh permanece.
        sess.token_hash = hash_token(access)
        sess.last_used_at = datetime.now(timezone.utc)  # noqa: UP017
        await self._session.flush()

        self_actor = Actor(
            actor_id=user.app_user_id,
            username=user.username,
            is_system=False,
        )
        await self._audit.record(
            actor=self_actor,
            action=AuditAction.AUTH_REFRESH,
            result=AuditResult.SUCCESS,
            entity_type="app_user",
            entity_id=user.app_user_id,
            extra={"session_id": str(sess.app_user_session_id)},
        )
        await self._session.commit()

        log.info(
            "auth.refresh",
            app_user_id=str(user.app_user_id),
            session_id=str(sess.app_user_session_id),
            actor=user.username,
        )
        return AccessTokenResponse(
            access_token=access,
            token_type="bearer",
            expires_in=self._access_ttl_seconds(),
        )

    async def logout(self, *, session_id: UUID, actor: Actor) -> None:
        await self._sessions.revoke_by_id(session_id)

        if actor.actor_id is not None:
            await self._audit.record(
                actor=actor,
                action=AuditAction.AUTH_LOGOUT,
                result=AuditResult.SUCCESS,
                entity_type="app_user",
                entity_id=actor.actor_id,
                extra={"session_id": str(session_id)},
            )
        await self._session.commit()
        log.info("auth.logout", session_id=str(session_id), actor=actor.username)

    async def change_password(
        self, *, app_user_id: UUID, data: ChangePasswordRequest, actor: Actor
    ) -> None:
        user = await self._users.get_by_id(app_user_id)
        if user is None:
            raise AppUserNotFound(app_user_id)
        if not verify_password(user.password_hash, data.current_password):
            raise CurrentPasswordInvalid()

        user.password_hash = hash_password(data.new_password)
        user.must_change_password = False
        # Forca novo login em todos os dispositivos após a troca.
        await self._sessions.revoke_all_for_user(app_user_id)
        await self._session.flush()
        await self._audit.record(
            actor=actor,
            action=AuditAction.AUTH_PASSWORD_CHANGED,
            result=AuditResult.SUCCESS,
            entity_type="app_user",
            entity_id=app_user_id,
            extra={"revoked_all_sessions": True},
        )
        await self._session.commit()

        log.info(
            "auth.password_changed",
            app_user_id=str(app_user_id),
            actor=actor.username,
        )
