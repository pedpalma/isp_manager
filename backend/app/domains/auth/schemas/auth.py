# Schemas Pydantic V2 dos fluxos de autenticação

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class TokenResponse(BaseModel):
    """Resposta do login: par access/refresh + metadados úteis ao cliente."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    # Validade do ACCESS token em segundos
    expires_in: int
    must_change_password: bool


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class AccessTokenResponse(BaseModel):
    """Resposta do refresh: apenas um novo access token (o refresh segue o
    mesmo no V1, sem rotação do refresh.)"""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


class MeRead(BaseModel):
    """Resposta do GET /auth/me. Inclui as permissões do grupo para o
    frontend conseguir gatear a UI. Sem timestamps ou campos sensíveis."""

    app_user_id: UUID
    user_group_id: UUID
    username: str
    email: str
    active: bool
    must_change_password: bool
    permissions: dict[str, Any]
