# Testes unit da função resolve_policies_for_onu.
# Sem DB. Foco na regra "mais específico ganha" e na cobertura de todas
# as metrics suportadas (None quando não ha politica).

from __future__ import annotations

from uuid import uuid4

from app.domains.optical.enums import (
    SUPPORTED_OPTICAL_METRICS,
    OpticalScopeType,
    OpticalSeverity,
)
from app.domains.optical.models.optical_threshold_policy import (
    OpticalThresholdPolicy,
)
from app.domains.optical.services.threshold_cache import resolve_policies_for_onu


def _make_policy(
    scope_type: OpticalScopeType,
    metric: str,
    *,
    scope_id=None,
    severity: OpticalSeverity = OpticalSeverity.WARNING,
    threshold_min: float | None = None,
    threshold_max: float | None = None,
) -> OpticalThresholdPolicy:
    policy = OpticalThresholdPolicy(
        scope_type=scope_type,
        scope_id=scope_id,
        metric_name=metric,
        threshold_min=threshold_min,
        threshold_max=threshold_max,
        severity=severity,
        active=True,
    )
    # Preenche manualmente o PK que normalmente seria gerado pelo banco.
    policy.optical_threshold_policy_id = uuid4()
    return policy


def test_resolution_covers_all_supported_metrics():
    result = resolve_policies_for_onu([])
    # Sem politicas, todas as metrics suportadas devolvem None.
    assert set(result.keys()) == SUPPORTED_OPTICAL_METRICS
    assert all(v is None for v in result.values())


def test_resolution_picks_onu_over_pon_over_olt_over_global():
    onu_policy = _make_policy(
        OpticalScopeType.ONU, "rx_power_dbm", scope_id=uuid4(), threshold_min=-25
    )
    pon_policy = _make_policy(
        OpticalScopeType.PON_PORT, "rx_power_dbm", scope_id=uuid4(), threshold_min=-26
    )
    olt_policy = _make_policy(
        OpticalScopeType.OLT, "rx_power_dbm", scope_id=uuid4(), threshold_min=-27
    )
    global_policy = _make_policy(OpticalScopeType.GLOBAL, "rx_power_dbm", threshold_min=-28)
    result = resolve_policies_for_onu([global_policy, olt_policy, pon_policy, onu_policy])
    chosen = result["rx_power_dbm"]
    assert chosen is not None
    assert chosen.scope_type == OpticalScopeType.ONU
    assert chosen.threshold_min == -25


def test_resolution_falls_back_to_olt_when_no_onu_or_pon():
    olt_policy = _make_policy(
        OpticalScopeType.OLT, "tx_power_dbm", scope_id=uuid4(), threshold_max=5
    )
    global_policy = _make_policy(OpticalScopeType.GLOBAL, "tx_power_dbm", threshold_max=10)
    result = resolve_policies_for_onu([global_policy, olt_policy])
    chosen = result["tx_power_dbm"]
    assert chosen is not None
    assert chosen.scope_type == OpticalScopeType.OLT
    assert chosen.threshold_max == 5


def test_resolution_uses_global_as_last_resort():
    global_policy = _make_policy(OpticalScopeType.GLOBAL, "temperature", threshold_max=80)
    result = resolve_policies_for_onu([global_policy])
    chosen = result["temperature"]
    assert chosen is not None
    assert chosen.scope_type == OpticalScopeType.GLOBAL


def test_resolution_isolates_metrics():
    # Politica em rx não afeta tx.
    rx_global = _make_policy(OpticalScopeType.GLOBAL, "rx_power_dbm", threshold_min=-28)
    result = resolve_policies_for_onu([rx_global])
    assert result["rx_power_dbm"] is not None
    assert result["tx_power_dbm"] is None
