# Cache TTL in-process para resolução hierárquica de thresholds.
# TTL curto (60s default, configurável) sem invalidação ativa.
# Aceito ate 60s de stale após mudança de policy.

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass
from threading import RLock
from uuid import UUID

from app.domains.optical.enums import (
    SCOPE_PRIORITY_ORDER,
    SUPPORTED_OPTICAL_METRICS,
    OpticalScopeType,
)
from app.domains.optical.models.optical_threshold_policy import (
    OpticalThresholdPolicy,
)
from app.domains.optical.schemas.effective_thresholds import EffectiveThreshold


@dataclass(slots=True)
class _Entry:
    value: EffectiveThreshold | None
    expires_at: float


def resolve_policies_for_onu(
    policies: Sequence[OpticalThresholdPolicy],
) -> dict[str, EffectiveThreshold | None]:
    """Resolve a hierarquia de scope para cada métrica suportada.
    Recebe TODAS as policies que podem afetar a ONU e devolve
    dict cobrindo TODAS as metrics suportadas."""
    # Indexa por (metric_name, scope_type) -> primeira policy ativa.
    by_metric_scope: dict[tuple[str, OpticalScopeType], OpticalThresholdPolicy] = {}
    for policy in policies:
        key = (policy.metric_name, policy.scope_type)
        # Em principio so existe UMA ativa por par;
        by_metric_scope.setdefault(key, policy)

    out: dict[str, EffectiveThreshold | None] = {}
    for metric in SUPPORTED_OPTICAL_METRICS:
        chosen: OpticalThresholdPolicy | None = None
        for scope in SCOPE_PRIORITY_ORDER:
            candidate = by_metric_scope.get((metric, scope))
            if candidate is not None:
                chosen = candidate
                break
        if chosen is None:
            out[metric] = None
        else:
            out[metric] = EffectiveThreshold(
                metric_name=metric,
                optical_threshold_policy_id=chosen.optical_threshold_policy_id,
                scope_type=chosen.scope_type,
                scope_id=chosen.scope_id,
                threshold_min=chosen.threshold_min,
                threshold_max=chosen.threshold_max,
                severity=chosen.severity,
            )
    return out


class ThresholdCache:
    """Cache in-process com TTL fixo. Thread-safe via RLock."""

    def __init__(self, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds deve ser > 0")
        self._ttl = ttl_seconds
        self._store: dict[tuple[UUID, str], _Entry] = {}
        self._lock = RLock()

    def get(self, onu_id: UUID, metric: str) -> EffectiveThreshold | None | _Sentinel:
        """Devolve a entrada cacheada ou _MISS quando ausente/expirada.
        None é valor válido (significa 'não ha policy aplicável')."""
        now = time.monotonic()
        key = (onu_id, metric)
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return _MISS
            if entry.expires_at <= now:
                # Expirada; limpa preguiçosamente.
                self._store.pop(key, None)
                return _MISS
            return entry.value

    def put_bulk(
        self,
        onu_id: UUID,
        thresholds: dict[str, EffectiveThreshold | None],
    ) -> None:
        """Insere todas as metrics de uma ONU de uma vez. Útil porque a
        resolução hierárquica já produz dict cobrindo todas as metrics."""
        now = time.monotonic()
        expires_at = now + self._ttl
        with self._lock:
            for metric, value in thresholds.items():
                self._store[(onu_id, metric)] = _Entry(value=value, expires_at=expires_at)

    def invalidate_onu(self, onu_id: UUID) -> None:
        """Remove todas as entradas de uma ONU. Útil em testes."""
        with self._lock:
            for key in list(self._store.keys()):
                if key[0] == onu_id:
                    self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


class _Sentinel:
    """Marca cache miss para diferenciar de None (valor válido)."""

    __slots__ = ()


_MISS = _Sentinel()


def is_miss(value: EffectiveThreshold | None | _Sentinel) -> bool:
    return isinstance(value, _Sentinel)
