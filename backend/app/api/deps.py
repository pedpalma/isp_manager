# Dependências compartilhadas entre rotas (`Depends(...)` do FastAPI).

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor, system_actor
from app.db.session import get_session
from app.domains.auth.exceptions import InvalidToken, PermissionDenied
from app.domains.auth.repositories.app_user_session import AppUserSessionRepository
from app.domains.auth.security import TOKEN_TYPE_ACCESS, decode_token


def get_current_actor() -> Actor:
    """Devolve o ator atual da requisição.

    Hoje sempre retorna `system_actor()` porque ainda não temos autenticação.
    Quando o Marco de Auth chegar, este helper passa a:
    1) ler `Authorization: Bearer ...` da requisição,
    2) validar o JWT,
    3) construir um `Actor` real com `actor_id` e `username` do token.

    Os services não precisam saber de nada disso: continuam recebendo
    `actor: Actor` e a fonte de verdade da identidade vive AQUI.
    """
    return system_actor()


# Esquema Bearer. auto_error=False
_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class CurrentUser:
    """Principal autenticado, resolvido a partir do access token. Carrega o
    suficiente para autorizar (permissions) e para montar o Actor passado
    aos services, sem novas queries."""

    app_user_id: UUID
    username: str
    email: str
    user_group_id: UUID
    active: bool
    must_change_password: bool
    permissions: dict[str, Any]
    session_id: UUID

    @property
    def is_admin(self) -> bool:
        # V1: {"all": true} concede tudo. Permissões finas ficam para depois.
        return bool(self.permissions.get("all"))

    def to_actor(self) -> Actor:
        return Actor(
            actor_id=self.app_user_id,
            username=self.username,
            is_system=False,
        )


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> CurrentUser:
    """Válida o access token e resolve sessão + usuário + grupo em uma query.
    Aqui acontece a verificação de revogação stateful-seletiva: só as
    rotas que dependem desta função pagam a consulta a app_user_session."""
    if creds is None or not creds.credentials:
        raise InvalidToken()

    try:
        payload = decode_token(creds.credentials)
    except jwt.InvalidTokenError as exc:
        raise InvalidToken() from exc

    if payload.get("type") != TOKEN_TYPE_ACCESS:
        raise InvalidToken()
    jti = payload.get("jti")
    if not jti:
        raise InvalidToken()
    try:
        session_id = UUID(jti)
    except (ValueError, TypeError) as exc:
        raise InvalidToken() from exc

    row = await AppUserSessionRepository(session).get_active_principal(session_id)
    if row is None:
        raise InvalidToken()
    sess, user, group = row

    return CurrentUser(
        app_user_id=user.app_user_id,
        username=user.username,
        email=user.email,
        user_group_id=user.user_group_id,
        active=user.active,
        must_change_password=user.must_change_password,
        permissions=dict(group.permissions_json or {}),
        session_id=sess.app_user_session_id,
    )


async def require_admin(
    current: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """Exige permissão administrativa. Usado nas rotas /user-groups e /app-users."""
    if not current.is_admin:
        raise PermissionDenied()
    return current
