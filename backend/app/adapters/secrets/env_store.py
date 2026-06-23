# Implementação env-var do SecretStore

# Valida o que é string not empty e not raw whitespace
#  TODO: Substituir essa implementação por vault_store via COLLECTION_SECRET_STORE=vault

from __future__ import annotations

import os

from app.adapters.secrets.base import SecretStore
from app.core.exceptions import ConfigurationError

# *Lista de forbidden chars
_FORBIDDEN_CHARS = frozenset(["/", "\\", "'", '"', "\n", "\t", "\r"])


def _validate_ref(ref: str) -> str:
    if not isinstance(ref, str):
        raise ConfigurationError(
            "secret_ref deve ser string.",
            details={"secret_ref_type": type(ref).__name__},
        )
    stripped = ref.strip()
    if not stripped:
        raise ConfigurationError(
            "secret_ref vazio.",
            details={"secret_ref": ref},
        )
    if any(c in _FORBIDDEN_CHARS for c in stripped):
        raise ConfigurationError(
            "secret_ref contém chars proíbidos.",
            details={"secret_ref": ref},
        )
    return stripped


class EnvSecretStore(SecretStore):
    def resolve(self, secret_ref: str) -> str:
        name = _validate_ref(secret_ref)
        value = os.environ.get(name)
        if value is None:
            raise ConfigurationError(
                f"Váriavel de ambiente '{name}' não definida.",
                details={"secret_ref": name},
            )
        if value == "":
            raise ConfigurationError(
                f"Váriavel de ambiente '{name}' vazia.",
                details={"secret_ref": name},
            )
        return value
