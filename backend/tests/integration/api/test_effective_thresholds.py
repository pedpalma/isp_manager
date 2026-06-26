# Testes de integração do endpoint GET /onus/{id}/effective-thresholds.

from __future__ import annotations

from uuid import uuid4

from tests.integration.api._olt_mock import setup_inventory
from tests.integration.api._optical_mock import create_onu_for_pon
from tests.integration.api.test_auth import _bootstrap_admin

API = "/api/v1"


def _create_onu_model(real_client, headers, manufacturer_id):
    r = real_client.post(
        f"{API}/onu-models",
        headers=headers,
        json={
            "manufacturer_id": str(manufacturer_id),
            "model": f"pytest-onum-{uuid4().hex[:8]}",
            "active": True,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["onu_model_id"]


def test_returns_all_metrics_as_none_when_no_policies(real_client):
    headers, _ = _bootstrap_admin(real_client)
    inv = setup_inventory(real_client, headers)
    onu_model_id = _create_onu_model(real_client, headers, inv["manufacturer_id"])
    onu = create_onu_for_pon(
        real_client,
        headers,
        pon_port_id=inv["pon_port_id"],
        onu_model_id=onu_model_id,
    )
    r = real_client.get(
        f"{API}/onus/{onu['onu_id']}/effective-thresholds",
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["onu_id"] == onu["onu_id"]
    # Todas as métricas existem como chave, todas com valor None.
    assert "rx_power_dbm" in body["thresholds"]
    assert "tx_power_dbm" in body["thresholds"]
    assert all(v is None for v in body["thresholds"].values())


def test_global_policy_shows_in_effective(real_client):
    headers, _ = _bootstrap_admin(real_client)
    inv = setup_inventory(real_client, headers)
    onu_model_id = _create_onu_model(real_client, headers, inv["manufacturer_id"])
    onu = create_onu_for_pon(
        real_client,
        headers,
        pon_port_id=inv["pon_port_id"],
        onu_model_id=onu_model_id,
    )
    real_client.post(
        f"{API}/optical-threshold-policies",
        headers=headers,
        json={
            "scope_type": "global",
            "metric_name": "rx_power_dbm",
            "threshold_min": -30.0,
            "threshold_max": -8.0,
            "severity": "warning",
        },
    )
    r = real_client.get(
        f"{API}/onus/{onu['onu_id']}/effective-thresholds",
        headers=headers,
    )
    assert r.status_code == 200
    rx = r.json()["thresholds"]["rx_power_dbm"]
    assert rx is not None
    assert rx["scope_type"] == "global"
    assert rx["threshold_min"] == -30.0
    # tx ainda não tem policy
    assert r.json()["thresholds"]["tx_power_dbm"] is None


def test_onu_specific_policy_wins_over_global(real_client):
    headers, _ = _bootstrap_admin(real_client)
    inv = setup_inventory(real_client, headers)
    onu_model_id = _create_onu_model(real_client, headers, inv["manufacturer_id"])
    onu = create_onu_for_pon(
        real_client,
        headers,
        pon_port_id=inv["pon_port_id"],
        onu_model_id=onu_model_id,
    )
    real_client.post(
        f"{API}/optical-threshold-policies",
        headers=headers,
        json={
            "scope_type": "global",
            "metric_name": "rx_power_dbm",
            "threshold_min": -30.0,
        },
    )
    real_client.post(
        f"{API}/optical-threshold-policies",
        headers=headers,
        json={
            "scope_type": "onu",
            "scope_id": onu["onu_id"],
            "metric_name": "rx_power_dbm",
            "threshold_min": -25.0,
        },
    )
    r = real_client.get(
        f"{API}/onus/{onu['onu_id']}/effective-thresholds",
        headers=headers,
    )
    assert r.status_code == 200
    rx = r.json()["thresholds"]["rx_power_dbm"]
    assert rx is not None
    assert rx["scope_type"] == "onu"
    assert rx["threshold_min"] == -25.0


def test_unknown_onu_returns_404(real_client):
    headers, _ = _bootstrap_admin(real_client)
    r = real_client.get(
        f"{API}/onus/{uuid4()}/effective-thresholds",
        headers=headers,
    )
    assert r.status_code == 404


def test_without_auth_returns_401(real_client):
    r = real_client.get(f"{API}/onus/{uuid4()}/effective-thresholds")
    assert r.status_code == 401
