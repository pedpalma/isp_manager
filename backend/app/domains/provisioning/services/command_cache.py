# Cache TTL in-process para resolução de normalized_command.


from __future__ import annotations

import time
from dataclasses import dataclass
from threading import RLock
from uuid import UUID


@dataclass(frozen=True, slots=True)
class NormalizedCommandResolved:
    """Snapshot imutável do que o worker precisa para renderizar e executar
    um comando resolvido. Frozen porque instâncias vivem no cache
    compartilhado entre threads/greenlets do worker."""

    normalized_command_id: UUID
    template_string: str
    output_parser: str | None
    timeout_ms: int
    requires_privileged: bool


CacheKey = tuple[UUID, UUID | None, str, str | None]
"""(manufacturer_id, olt_model_id, command_key, version_constraint).

Ordem espelha o índice parcial uq_normalized_command_active do DDL."""


@dataclass(slots=True)
class _Entry:
    value: NormalizedCommandResolved | None
    expires_at: float


class _Sentinel:
    """Diferencia cache miss de None (valor válido cacheado)."""

    __slots__ = ()


_MISS = _Sentinel()


def is_miss(value: NormalizedCommandResolved | None | _Sentinel) -> bool:
    return isinstance(value, _Sentinel)


class CommandCache:
    """Cache TTL para NormalizedCommand resolvidos. Thread-safe via RLock.

    Uso típico no worker:
        cached = cache.get(key)
        if is_miss(cached):
            resolved = _query_db(key)  # pode retornar None
            cache.put(key, resolved)
            cached = resolved
        # cached agora é NormalizedCommandResolved | None
    """

    def __init__(self, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds deve ser > 0")
        self._ttl = ttl_seconds
        self._store: dict[CacheKey, _Entry] = {}
        self._lock = RLock()

    def get(self, key: CacheKey) -> NormalizedCommandResolved | None | _Sentinel:
        """Retorna valor cacheado ou _MISS se ausente/expirado.

        None é valor cacheável válido (comando não existe no catálogo).
        Use is_miss(result) para distinguir."""
        now = time.monotonic()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return _MISS
            if entry.expires_at <= now:
                # Expirado: limpa preguiçosamente.
                self._store.pop(key, None)
                return _MISS
            return entry.value

    def put(self, key: CacheKey, value: NormalizedCommandResolved | None) -> None:
        """Grava valor (incluindo None) com TTL atual."""
        expires_at = time.monotonic() + self._ttl
        with self._lock:
            self._store[key] = _Entry(value=value, expires_at=expires_at)

    def invalidate(self, key: CacheKey) -> None:
        """Remove uma entrada específica. Útil em testes."""
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
