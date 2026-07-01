# Testes unitários do contrato OltAdapter e do MockOltAdapter.

from __future__ import annotations

from uuid import uuid4

import pytest

from app.adapters.olt.base import (
    CommandLog,
    DiscoveredOnu,
    DiscoveryResult,
    OltAdapter,
    OltConnectionConfig,
    OnuLocator,
    OnuState,
    PlannedCommand,
    ProvisioningPlan,
    ProvisioningResult,
    StepResult,
)
from app.adapters.olt.mock import (
    MockOltAdapter,
    clear_canned_discovery,
    clear_canned_onu_state,
    clear_canned_provisioning,
    set_canned_discovery,
    set_canned_onu_state,
    set_canned_provisioning,
)


def _cfg() -> OltConnectionConfig:
    return OltConnectionConfig(
        host="10.0.0.1",
        port=22,
        protocol="SSH",
        username="admin",
        password="secret",
    )


def _plan(*keys: str) -> ProvisioningPlan:
    """Monta um ProvisioningPlan com um PlannedCommand por chave informada."""
    return ProvisioningPlan(
        locator=OnuLocator(slot_index=1, pon_index=1, serial="AAAA1"),
        commands=[
            PlannedCommand(command_key=k, rendered=f"cmd::{k}", timeout_ms=5000) for k in keys
        ],
    )


def test_abc_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        OltAdapter()  # type: ignore[abstract]


def test_mock_returns_empty_without_canned():
    olt_id = uuid4()
    clear_canned_discovery(olt_id)
    adapter = MockOltAdapter()
    result = adapter.list_unprovisioned_onus(_cfg(), olt_id=olt_id)
    assert isinstance(result, DiscoveryResult)
    assert result.discovered == []
    # Mesmo sem ONUs, registra o log do comando para auditoria.
    assert len(result.command_logs) == 1
    assert result.command_logs[0].success is True


def test_mock_returns_canned_payload():
    olt_id = uuid4()
    set_canned_discovery(
        olt_id,
        [
            {"serial": "AAAA1", "slot_index": 1, "pon_index": 2, "vendor_id": "ALCL"},
            {"serial": "BBBB2", "slot_index": 1, "pon_index": 3},
        ],
    )
    try:
        adapter = MockOltAdapter()
        result = adapter.list_unprovisioned_onus(_cfg(), olt_id=olt_id)
        assert len(result.discovered) == 2
        first = result.discovered[0]
        assert isinstance(first, DiscoveredOnu)
        assert first.serial == "AAAA1"
        assert first.slot_index == 1
        assert first.pon_index == 2
        assert first.vendor_id == "ALCL"
        assert first.raw_payload["serial"] == "AAAA1"
    finally:
        clear_canned_discovery(olt_id)


def test_mock_health_returns_true():
    assert MockOltAdapter().health(_cfg()) is True


def test_command_log_defaults():
    log = CommandLog(step_name="x", command_sent="y")
    assert log.success is True
    assert log.duration_ms is None


def test_discovered_onu_immutable():
    d = DiscoveredOnu(serial="X", slot_index=1, pon_index=1)
    with pytest.raises((AttributeError, Exception)):
        d.serial = "Y"  # type: ignore[misc]


# provision_onu / deprovision_onu / get_onu_state
def test_provision_default_echoes_plan():
    """Sem canned, o mock ecoa cada comando do plano como passo bem-sucedido."""
    olt_id = uuid4()
    clear_canned_provisioning(olt_id)
    adapter = MockOltAdapter()
    result = adapter.provision_onu(_cfg(), _plan("authorize_onu", "bind_vlan"), olt_id=olt_id)
    assert isinstance(result, ProvisioningResult)
    assert result.overall_success is True
    assert len(result.steps) == 2
    assert isinstance(result.steps[0], StepResult)
    # command_sent reflete o rendered do PlannedCommand, na ordem do plano.
    assert result.steps[0].command_sent == "cmd::authorize_onu"
    assert result.steps[1].command_sent == "cmd::bind_vlan"
    assert all(s.success for s in result.steps)


def test_provision_uses_canned_and_computes_overall():
    """Com canned e sem overall explícito, overall_success = all(step.success)."""
    olt_id = uuid4()
    set_canned_provisioning(
        olt_id,
        [
            {"command_sent": "step-1", "success": True},
            {"command_sent": "step-2", "success": False, "output_received": "erro X"},
        ],
    )
    try:
        result = MockOltAdapter().provision_onu(_cfg(), _plan("x"), olt_id=olt_id)
        assert len(result.steps) == 2
        assert result.steps[1].success is False
        assert result.steps[1].output_received == "erro X"
        assert result.overall_success is False
    finally:
        clear_canned_provisioning(olt_id)


def test_provision_canned_overall_explicit_overrides():
    """overall_success explícito prevalece mesmo com um passo falho."""
    olt_id = uuid4()
    set_canned_provisioning(
        olt_id,
        [{"command_sent": "step-1", "success": False}],
        overall_success=True,
    )
    try:
        result = MockOltAdapter().provision_onu(_cfg(), _plan("x"), olt_id=olt_id)
        assert result.steps[0].success is False
        assert result.overall_success is True
    finally:
        clear_canned_provisioning(olt_id)


def test_deprovision_shares_canned_with_provision():
    """deprovision_onu lê o mesmo canned de provisionamento."""
    olt_id = uuid4()
    set_canned_provisioning(olt_id, [{"command_sent": "delete-onu", "success": True}])
    try:
        result = MockOltAdapter().deprovision_onu(_cfg(), _plan("delete_onu"), olt_id=olt_id)
        assert result.overall_success is True
        assert result.steps[0].command_sent == "delete-onu"
    finally:
        clear_canned_provisioning(olt_id)


def test_get_onu_state_default():
    """Sem canned, get_onu_state devolve estado operacional fake determinístico."""
    olt_id = uuid4()
    clear_canned_onu_state(olt_id)
    locator = OnuLocator(slot_index=1, pon_index=1, serial="AAAA1")
    state = MockOltAdapter().get_onu_state(_cfg(), locator, olt_id=olt_id)
    assert isinstance(state, OnuState)
    assert state.admin_status == "active"
    assert state.operational_status == "online"
    assert state.raw_payload["mock"] is True
    assert state.raw_payload["locator_serial"] == "AAAA1"


def test_get_onu_state_uses_canned():
    olt_id = uuid4()
    set_canned_onu_state(
        olt_id,
        {"admin_status": "disabled", "operational_status": "offline", "raw_payload": {"k": 1}},
    )
    try:
        locator = OnuLocator(slot_index=1, pon_index=1, serial="AAAA1")
        state = MockOltAdapter().get_onu_state(_cfg(), locator, olt_id=olt_id)
        assert state.admin_status == "disabled"
        assert state.operational_status == "offline"
        assert state.raw_payload == {"k": 1}
    finally:
        clear_canned_onu_state(olt_id)


def test_olt_id_is_keyword_only_on_provision():
    """olt_id é keyword-only: chamada posicional levanta TypeError."""
    adapter = MockOltAdapter()
    with pytest.raises(TypeError):
        adapter.provision_onu(_cfg(), _plan("x"), uuid4())  # type: ignore[misc]


def test_provisioning_result_immutable():
    r = ProvisioningResult(steps=[], overall_success=True)
    with pytest.raises((AttributeError, Exception)):
        r.overall_success = False  # type: ignore[misc]
