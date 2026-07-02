# Testes unitários do CommandCache

from __future__ import annotations

import time
from uuid import uuid4

import pytest

from app.domains.provisioning.services.command_cache import (
    CacheKey,
    CommandCache,
    NormalizedCommandResolved,
    is_miss,
)


def _make_resolved() -> NormalizedCommandResolved:
    return NormalizedCommandResolved(
        normalized_command_id=uuid4(),
        template_string="show onu {onu_index}",
        output_parser=None,
        timeout_ms=5000,
        requires_privileged=False,
    )


def _make_key() -> CacheKey:
    return (uuid4(), uuid4(), "show-onu", None)


def test_get_miss_on_empty_cache() -> None:
    cache = CommandCache(ttl_seconds=60)
    result = cache.get(_make_key())
    assert is_miss(result)


def test_put_and_get_hit() -> None:
    cache = CommandCache(ttl_seconds=60)
    key = _make_key()
    resolved = _make_resolved()

    cache.put(key, resolved)
    got = cache.get(key)

    assert not is_miss(got)
    assert got is resolved


def test_none_is_cacheable_and_distinguishable_from_miss() -> None:
    """None tem cache válido"""
    cache = CommandCache(ttl_seconds=60)
    key = _make_key()

    cache.put(key, None)
    got = cache.get(key)

    assert got is None
    assert not is_miss(got)


def test_expiration_returns_miss() -> None:
    """TTL de 0.5ms: espera 1ms e checa que expirou"""
    cache = CommandCache(ttl_seconds=1)
    key = _make_key()
    cache.put(key, _make_resolved())

    cache._ttl = 0

    with cache._lock:
        entry = list(cache._store.values())[0]
        entry.expires_at = time.monotonic() - 1.0

    result = cache.get(key)
    assert is_miss(result)


def test_ttl_zero_or_negative_raises() -> None:
    with pytest.raises(ValueError):
        CommandCache(ttl_seconds=0)
    with pytest.raises(ValueError):
        CommandCache(ttl_seconds=-1)


def test_invalidate_removes_entry() -> None:
    cache = CommandCache(ttl_seconds=60)
    key = _make_key()
    cache.put(key, _make_resolved())

    cache.invalidate(key)

    assert is_miss(cache.get(key))


def test_clear_empties_all_entries() -> None:
    cache = CommandCache(ttl_seconds=60)
    key_a = _make_key()
    key_b = _make_key()
    cache.put(key_a, _make_resolved())
    cache.put(key_b, _make_resolved())

    cache.clear()

    assert is_miss(cache.get(key_a))
    assert is_miss(cache.get(key_b))

    def test_different_keys_are_isolated() -> None:
        """Chaves com manufacturer_id diferente NÃO devem colidir."""
        cache = CommandCache(ttl_seconds=60)
        resolved_a = _make_resolved()
        resolved_b = _make_resolved()
        key_a: CacheKey = (uuid4(), None, "show-onu", None)
        key_b: CacheKey = (uuid4(), None, "show-onu", None)

        cache.put(key_a, resolved_a)
        cache.put(key_b, resolved_b)

        assert cache.get(key_a) is resolved_a
        assert cache.get(key_b) is resolved_b


def test_version_constraint_is_part_of_key() -> None:
    """versões diferentes = chaves diferentes."""
    cache = CommandCache(ttl_seconds=60)
    manufacturer_id = uuid4()
    olt_model_id = uuid4()
    resolved_v1 = _make_resolved()
    resolved_v2 = _make_resolved()

    key_v1: CacheKey = (manufacturer_id, olt_model_id, "show-onu", "1.0")
    key_v2: CacheKey = (manufacturer_id, olt_model_id, "show-onu", "2.0")

    cache.put(key_v1, resolved_v1)
    cache.put(key_v2, resolved_v2)

    assert cache.get(key_v1) is resolved_v1
    assert cache.get(key_v2) is resolved_v2


def test_resolved_dataclass_is_frozen() -> None:
    resolved = _make_resolved()
    with pytest.raises(Exception):  # noqa: B017
        resolved.timeout_ms = 999  # type: ignore[misc]
