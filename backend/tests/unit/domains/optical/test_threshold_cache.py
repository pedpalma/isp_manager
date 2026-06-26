# Testes unit do ThresholdCache.
# Sem DB. Foco em TTL, sentinela _MISS vs valor None válido, e invalidação.

from __future__ import annotations

import time
from uuid import uuid4

from app.domains.optical.enums import OpticalScopeType, OpticalSeverity
from app.domains.optical.schemas.effective_thresholds import EffectiveThreshold
from app.domains.optical.services.threshold_cache import (
    ThresholdCache,
    is_miss,
)


def _sample_threshold():
    return EffectiveThreshold(
        metric_name="rx_power_dbm",
        optical_threshold_policy_id=uuid4(),
        scope_type=OpticalScopeType.GLOBAL,
        scope_id=None,
        threshold_min=-30.0,
        threshold_max=-8.0,
        severity=OpticalSeverity.WARNING,
    )


def test_cache_returns_miss_when_empty():
    cache = ThresholdCache(ttl_seconds=60)
    result = cache.get(uuid4(), "rx_power_dbm")
    assert is_miss(result)


def test_cache_returns_value_after_put():
    cache = ThresholdCache(ttl_seconds=60)
    onu_id = uuid4()
    threshold = _sample_threshold()
    cache.put_bulk(onu_id, {"rx_power_dbm": threshold})
    result = cache.get(onu_id, "rx_power_dbm")
    assert not is_miss(result)
    assert result.optical_threshold_policy_id == threshold.optical_threshold_policy_id  # type: ignore


def test_cache_distinguishes_none_value_from_miss():
    # None e valor cacheavel válido (significa "sem policy").
    cache = ThresholdCache(ttl_seconds=60)
    onu_id = uuid4()
    cache.put_bulk(onu_id, {"rx_power_dbm": None})
    result = cache.get(onu_id, "rx_power_dbm")
    assert not is_miss(result)
    assert result is None


def test_cache_expires_after_ttl():
    cache = ThresholdCache(ttl_seconds=1)
    onu_id = uuid4()
    cache.put_bulk(onu_id, {"rx_power_dbm": _sample_threshold()})
    time.sleep(1.1)
    result = cache.get(onu_id, "rx_power_dbm")
    assert is_miss(result)


def test_cache_invalidate_onu_clears_all_metrics():
    cache = ThresholdCache(ttl_seconds=60)
    onu_id = uuid4()
    cache.put_bulk(
        onu_id,
        {
            "rx_power_dbm": _sample_threshold(),
            "tx_power_dbm": _sample_threshold(),
        },
    )
    cache.invalidate_onu(onu_id)
    assert is_miss(cache.get(onu_id, "rx_power_dbm"))
    assert is_miss(cache.get(onu_id, "tx_power_dbm"))


def test_cache_rejects_zero_ttl():
    try:
        ThresholdCache(ttl_seconds=0)
    except ValueError:
        pass
    else:
        raise AssertionError("ttl=0 deveria levantar ValueError")
