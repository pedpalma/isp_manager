# Factory de oltadapter.

# Escolha em runtime entre mock, fiberhome, zte.
# TODO: stubs fiberhome/zte com acesso ao lab.

# A factory é sem estado: instancia novo adapter por chamada.
# adapters são leves e thread-safe (nenhum guarda conexão);
# A conexão real é por chamada de list_unprovisioned_onus.

from __future__ import annotations

from app.adapters.olt.base import OltAdapter
from app.adapters.olt.mock import MockOltAdapter
from app.core.config import settings
from app.core.exceptions import ConfigurationError


def get_olt_adapter() -> OltAdapter:
    """Retorna o OltAdapter configurado em settings.collections.olt_adapter."""
    name = settings.collection.olt_adapter
    if name == "mock":
        return MockOltAdapter()
    if name in ("fiberhome", "zte"):
        # TODO: implementações reais
        raise ConfigurationError(
            f"Adapter de OLT '{name}' ainda não implementado.",
            details={"olt_adapter": name},
        )
    raise ConfigurationError(
        f"Adapter de OLT desconhecido: '{name}'.",
        details={"olt_adapter": name},
    )
