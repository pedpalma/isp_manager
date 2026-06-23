# Contrato comum dos adapters de secret store.

from __future__ import annotations

from abc import ABC, abstractmethod


class SecretStrore(ABC):
    @abstractmethod
    def resolve(self, secret_ref: str) -> str:
        """Resolve um ponteiro de secret para o valor.

        Levanta ConfigurationError se o ponteiro for
        inválido ou se o secret não puder ser resolvido."""
