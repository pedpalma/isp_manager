# Testes de integração do CRUD de optical_threshold_policy.

from __future__ import annotations

from uuid import uuid4

from tests.integration.api.test_auth import _bootstrap_admin

API = "/api/v1"


def test_create_global_policy_success(real_client):
    headers, _ = _bootstrap_admin(real_client)
    r = real_client.post(
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
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["scope_type"] == "global"
    assert body["scope_id"] is None
    assert body["threshold_min"] == -30.0


def test_create_global_with_scope_id_returns_400(real_client):
    headers, _ = _bootstrap_admin(real_client)
    r = real_client.post(
        f"{API}/optical-threshold-policies",
        headers=headers,
        json={
            "scope_type": "global",
            "scope_id": str(uuid4()),
            "metric_name": "rx_power_dbm",
            "threshold_min": -30.0,
        },
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "bad_request"


def test_create_olt_scope_without_scope_id_returns_400(real_client):
    headers, _ = _bootstrap_admin(real_client)
    r = real_client.post(
        f"{API}/optical-threshold-policies",
        headers=headers,
        json={
            "scope_type": "olt",
            "metric_name": "rx_power_dbm",
            "threshold_min": -30.0,
        },
    )
    assert r.status_code == 400


def test_create_with_invalid_metric_returns_422(real_client):
    headers, _ = _bootstrap_admin(real_client)
    r = real_client.post(
        f"{API}/optical-threshold-policies",
        headers=headers,
        json={
            "scope_type": "global",
            "metric_name": "metric_inexistente",
            "threshold_min": -30.0,
        },
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_create_without_thresholds_returns_422(real_client):
    headers, _ = _bootstrap_admin(real_client)
    r = real_client.post(
        f"{API}/optical-threshold-policies",
        headers=headers,
        json={
            "scope_type": "global",
            "metric_name": "rx_power_dbm",
        },
    )
    assert r.status_code == 422


def test_create_duplicate_active_returns_409(real_client):
    headers, _ = _bootstrap_admin(real_client)
    payload = {
        "scope_type": "global",
        "metric_name": "tx_power_dbm",
        "threshold_min": -10.0,
        "threshold_max": 5.0,
    }
    r1 = real_client.post(f"{API}/optical-threshold-policies", headers=headers, json=payload)
    assert r1.status_code == 201

    r2 = real_client.post(f"{API}/optical-threshold-policies", headers=headers, json=payload)
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "conflict"


def test_update_mutable_fields(real_client):
    headers, _ = _bootstrap_admin(real_client)
    r1 = real_client.post(
        f"{API}/optical-threshold-policies",
        headers=headers,
        json={
            "scope_type": "global",
            "metric_name": "temperature",
            "threshold_max": 80.0,
        },
    )
    policy_id = r1.json()["optical_threshold_policy_id"]

    r2 = real_client.patch(
        f"{API}/optical-threshold-policies/{policy_id}",
        headers=headers,
        json={"threshold_max": 75.0, "severity": "critical"},
    )
    assert r2.status_code == 200
    body = r2.json()
    assert body["threshold_max"] == 75.0
    assert body["severity"] == "critical"


def test_update_deactivate_then_recreate_active(real_client):
    headers, _ = _bootstrap_admin(real_client)
    payload = {
        "scope_type": "global",
        "metric_name": "voltage",
        "threshold_min": 2.7,
        "threshold_max": 3.6,
    }
    r1 = real_client.post(f"{API}/optical-threshold-policies", headers=headers, json=payload)
    policy_id_old = r1.json()["optical_threshold_policy_id"]

    # Desativa
    r_deact = real_client.patch(
        f"{API}/optical-threshold-policies/{policy_id_old}",
        headers=headers,
        json={"active": False},
    )
    assert r_deact.status_code == 200

    # Recria como ativa: agora deveria passar (índice parcial libera)
    r_new = real_client.post(f"{API}/optical-threshold-policies", headers=headers, json=payload)
    assert r_new.status_code == 201


def test_get_unknown_returns_404(real_client):
    headers, _ = _bootstrap_admin(real_client)
    r = real_client.get(f"{API}/optical-threshold-policies/{uuid4()}", headers=headers)
    assert r.status_code == 404


def test_list_with_filters(real_client):
    headers, _ = _bootstrap_admin(real_client)
    real_client.post(
        f"{API}/optical-threshold-policies",
        headers=headers,
        json={
            "scope_type": "global",
            "metric_name": "bias_current",
            "threshold_max": 100.0,
        },
    )
    r = real_client.get(
        f"{API}/optical-threshold-policies",
        headers=headers,
        params={"scope_type": "global", "metric_name": "bias_current"},
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert all(item["metric_name"] == "bias_current" for item in items)


def test_create_without_auth_returns_401(real_client):
    r = real_client.post(
        f"{API}/optical-threshold-policies",
        json={"scope_type": "global", "metric_name": "rx_power_dbm"},
    )
    assert r.status_code == 401
