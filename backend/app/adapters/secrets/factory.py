# Factory do SecretStore

from __future__ import annotations

from app.adapters.secrets.base import SecretStrore
from app.adapters.secrets.env_store import EnvSecretStore
from app.core.config import settings
from app.core.exceptions import ConfigurationError


def get_secret_store() -> SecretStrore:
    name = settings.collection.secret_store
    if name == "env":
        return EnvSecretStore()
    raise ConfigurationError(
        f"Secret store desconhecido: '{name}'.",
        details={"secret_store": name},
    )
