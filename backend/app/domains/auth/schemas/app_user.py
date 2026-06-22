# Schemas Pydantic v2 do AppUser.

# Regra sensível: `password_hash`, `reset_password_token` e
# `reset_password_expires_at` NUNCA aparecem no Read. A senha em claro entra
# apenas no Create; o service faz o hash argon2 e descarta o claro.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# Validação de E-mail leve, sem dependência extra (email-validator).
# Suficiente para V1: rejeita formatos obviamente inválidos.
# TODO: Implementar validação/normalização de e-mail a fundo.

_EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class AppUserCreate(BaseModel):
    """Corpo do POST /app-users (somente admin)."""

    user_group_id: UUID
    username: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=200, pattern=_EMAIL_PATTERN)
    # Senha em claro. Não é persistida: o service gera o HASH.
    password: str = Field(
        min_length=8,
        max_length=200,
        description="Senha em claro. O servidor armazena apenas o hash argon2.",
    )
    active: bool = Field(default=True)
    must_change_password: bool = Field(
        default=False, description="TRUE: o user será obrigado a trocar a senha após o login."
    )


class AppUserUpdate(BaseModel):
    """Corpo do PATCH /app-users/{is} (somente admin). Semântica PATCH.
    `username` é imutável (chave de unicidade). A senha NÃO se altera aqui:
    troca via POST /auth/change-password (self-service)."""

    user_group_id: UUID | None = None
    email: str | None = Field(
        default=None,
        min_length=3,
        max_length=200,
        pattern=_EMAIL_PATTERN,
    )
    active: bool | None = None
    must_change_password: bool | None = None


class AppUserRead(BaseModel):
    """Resposta de leitura. NÃO expõe password_hash nem campos de reset."""

    model_config = ConfigDict(from_attributes=True)

    app_user_id: UUID
    user_group_id: UUID
    username: str
    email: str
    active: bool
    must_change_password: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime
