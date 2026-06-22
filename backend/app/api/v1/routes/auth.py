# Rotas de autenticação.

# Publicas: POST /auth/login, POST /auth/refresh.
# Autenticadas (qualquer usuário ativo): POST /auth/logout, GET /auth/me,
# POST /auth/change-password.

from __future__ import annotations

import ipaddress

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.db.session import get_session
from app.domains.auth.schemas.auth import (
    AccessTokenResponse,
    ChangePasswordRequest,
    LoginRequest,
    MeRead,
    RefreshRequest,
    TokenResponse,
)
from app.domains.auth.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_service(session: AsyncSession = Depends(get_session)) -> AuthService:
    return AuthService(session)


def _client_ip(request: Request) -> str | None:
    """IP do cliente, apenas se for um endereço valido.

    `request.client.host` nem sempre é um IP: o TestClient envia
    'testclient', e um proxy mal configurado pode injetar lixo. A coluna
    `app_user_session.ip_address` é INET, então gravar um não-IP estoura o
    INSERT (asyncpg DataError). Saneamos na borda: o que não parsear vira None.
    Auditoria de IP é best-effort, não pode derrubar o login."""
    if request.client is None:
        return None
    host = request.client.host
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return None
    return host


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    user_agent = request.headers.get("user-agent")
    return await service.login(payload, ip_address=_client_ip(request), user_agent=user_agent)


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    payload: RefreshRequest,
    service: AuthService = Depends(get_auth_service),
) -> AccessTokenResponse:
    return await service.refresh(payload)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    current: CurrentUser = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
) -> None:
    await service.logout(session_id=current.session_id, actor=current.to_actor())


@router.get("/me", response_model=MeRead)
async def me(current: CurrentUser = Depends(get_current_user)) -> MeRead:
    return MeRead(
        app_user_id=current.app_user_id,
        user_group_id=current.user_group_id,
        username=current.username,
        email=current.email,
        active=current.active,
        must_change_password=current.must_change_password,
        permissions=current.permissions,
    )


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: ChangePasswordRequest,
    current: CurrentUser = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
) -> None:
    await service.change_password(
        app_user_id=current.app_user_id, data=payload, actor=current.to_actor()
    )
