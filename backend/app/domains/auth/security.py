# Primitiva de segurança do domínio de autenticação

# Três responsabilidades, deliberadamente separadas:
# 1. Hash de SENHA (argon2): não reversível. Usado para guardar `app_user.password_hash` e verificar no login.
#  Nunca é determinístico, portanto NÃO serve para lookup por igualdade.
# 2. Hash de TOKEN (sha256): determinístico. Os tokens JWT ja sao de alta entropia;
#  guardamos apenas o digest em `app_user_session.token_hash` (UNIQUE) para conseguir localizar/revogar
#  a sessão sem armazenar o token cru. Por ser determinístico, permite busca por igualdade.
# 3. JWT (PyJWT, HS256): emissão e validação de access/refresh tokens.

# Este módulo NÃO importa exceções de domínio de propósito: deixa as
# exceções do PyJWT (subclasses de jwt.InvalidTokenError) propagarem para
# quem chama (deps.get_current_user e AuthService.refresh), que traduzem
# para AuthenticationError. Mantém a primitiva pura.

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error

from app.core.config import settings

# Instância única do hasher
_ph = PasswordHasher()

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


# Senha
def hash_password(plain: str) -> str:
    """Gera o hash argon2 da senha. Resultado não determinístico.
    Guardar em `app_user.password_hash`."""
    return _ph.hash(plain)


def verify_password(stored_hash: str, plain: str) -> bool:
    """Verifica a senha correta contra o hash guardado. Retorna False em caso de falhas.
    O chamados decide a resposta (normalmente 401 genérico, sem revelar a causa)."""
    try:
        return _ph.verify(stored_hash, plain)
    except Argon2Error:
        return False


# Token
def hash_token(token: str) -> str:
    """Digest sha256 hex do token. Determinístico de propósito: é o que permite localizar
    a sessão por `token hash`/`refresh_token_hash` sem nunca persistir o token cru."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# JWT
def _encode(
    *,
    subject: str,
    session_id: str,
    token_type: str,
    expires_minutes: int,
    extra: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(timezone.utc)  # noqa: UP017
    payload: dict[str, Any] = {
        "sub": subject,
        "jti": session_id,
        "type": token_type,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(
        payload,
        settings.security.api_secret_key.get_secret_value(),
        algorithm=settings.security.jwt_algorithm,
    )


def create_access_token(*, subject: str, session_id: str) -> str:
    """Access token curto, `subject`=app_user_id, `jti`=app_user_session_id."""
    return _encode(
        subject=subject,
        session_id=session_id,
        token_type=TOKEN_TYPE_ACCESS,
        expires_minutes=settings.security.access_token_expire_minutes,
    )


def create_refresh_token(*, subject: str, session_id: str) -> str:
    """Refresh token longo. Mesmo `jti`do access emitido no login,
    para amarrar ambos a uma única linha de sessão."""
    return _encode(
        subject=subject,
        session_id=session_id,
        token_type=TOKEN_TYPE_ACCESS,
        expires_minutes=settings.security.refresh_token_expire_minutes,
    )


def encode_token(token: str) -> dict[str, Any]:
    """Decodifica e válida assinatura + expiração do token.
    Levanta jwt.InvalidTokenError (inclui ExpiredSignatureError)
    em qualquer problema. o chamador traduz para AuthenticationError."""
    return jwt.decode(
        token,
        settings.security.api_secret_key.get_secret_value(),
        algorithms=[settings.security.jwt_algorithm],
    )
