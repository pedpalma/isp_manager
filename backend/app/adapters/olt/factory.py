# Factory de OltAdapter.

from __future__ import annotations

from app.adapters.olt.base import OltAdapter
from app.adapters.olt.mock import MockOltAdapter
from app.core.config import settings
from app.core.exceptions import ConfigurationError

# Slugs mapeáveis. Qualquer outra string cai no default de settings.
# TODO: adicionar "huawei" quando entrar no roadmap.
_KNOWN_SLUGS: frozenset[str] = frozenset({"fiberhome", "zte"})


def get_olt_adapter(manufacturer_slug: str | None = None) -> OltAdapter:
    """Retorna o OltAdapter apropriado."""

    normalized_slug = manufacturer_slug.strip().lower() if manufacturer_slug else None

    if normalized_slug in _KNOWN_SLUGS:
        return _instantiate_by_name(normalized_slug)
    return _instantiate_by_name(settings.collection.olt_adapter)


def _instantiate_by_name(name: str) -> OltAdapter:
    """Traduz um nome canônico ('mock' | 'fiberhome' | 'zte') em uma
    instância de OltAdapter. Isolado para facilitar teste unitário
    da factory sem precisar mexer em settings."""
    if name == "mock":
        return MockOltAdapter()
    if name in _KNOWN_SLUGS:
        # Quando os adapters reais forem implementados, a instanciação vai passar por aqui.
        raise ConfigurationError(
            f"Adapter de OLT '{name}' ainda não implementado (aguardando spike com lab).",
            details={"olt_adapter": name},
        )
    raise ConfigurationError(
        f"Adapter de OLT desconhecido: '{name}'.",
        details={"olt_adapter": name},
    )
