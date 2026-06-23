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
)
from app.adapters.olt.mock import (
    MockOltAdapter,
    clear_canned_discovery,
    set_canned_discovery,
)


def _cfg() -> OltConnectionConfig:
    return OltConnectionConfig(
        host="10.0.0.1",
        port=22,
        protocol="SSH",
        username="admin",
        password="secret",
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
