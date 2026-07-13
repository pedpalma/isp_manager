# Mascaramento de secrets em payload de auditoria

# Substitui o valor das chaves em SENSITIVE_KEYS por ***

from __future__ import annotations

from typing import Any

SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        # Credenciais de acesso a OLT
        "secret_ref",
        "private_key_ref",
        # Autenticação de user
        "password",
        "password_hash",
        "reset_password_token",
        "refresh_token",
        "access_token",
        "token",
        "token_hash",
        "refresh_token_hash",
    }
)

MASK_STRING = "***"


def scrub_secrets(payload: Any) -> Any:
    """Devolve uma cópia do payload com valores sensíveis substituídos por MASK_STRING."""
    if payload is None:
        return None
    if isinstance(payload, dict):
        scrubbed: dict[str, Any] = {}
        for key, value in payload.items():
            if key in SENSITIVE_KEYS:
                scrubbed[key] = MASK_STRING
            else:
                scrubbed[key] = scrub_secrets(value)
        return scrubbed
    if isinstance(payload, (list, tuple)):
        return [scrub_secrets(item) for item in payload]
    return payload
