# Testes de integração das rotas /optical-alerts.
# Cenários cobertos pelo test_signal_reading_jobs.py: criação via worker,
# upsert logico, acknowledge, resolve.
# Aqui foco em casos de borda: detail/list filtros, 404, transições invalidas.

from __future__ import annotations

import os
from uuid import uuid4

from sqlalchemy import create_engine, text  # noqa: F401

from app.core.config import settings  # noqa: F401
from tests.integration.api._olt_mock import setup_inventory
from tests.integration.api._optical_mock import (
    clear_canned_optical_readings,
    create_onu_for_pon,
    set_canned_optical_readings,
)
from tests.integration.api.test_auth import _bootstrap_admin

API = "/api/v1"


def _ensure_secret_env():
    os.environ.setdefault("PYTEST_OLT_SECRET", "pytest-fake-pass")


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


def _generate_alert(real_client, headers, inv) -> tuple[str, str]:
    """Cria policy + ONU + gera 1 alerta via worker. Retorna (alert_id, onu_id)."""
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
        },
    )
    set_canned_optical_readings(
        inv["olt_id"],
        [{"serial": onu["serial"], "rx_power_dbm": -35.0}],
    )
    try:
        r = real_client.post(
            f"{API}/collection-jobs/signal-reading",
            headers=headers,
            json={"olt_id": str(inv["olt_id"])},
        )
        assert r.status_code == 202, r.text
    finally:
        clear_canned_optical_readings(inv["olt_id"])

    rl = real_client.get(
        f"{API}/optical-alerts",
        headers=headers,
        params={"onu_id": onu["onu_id"]},
    )
    return rl.json()["items"][0]["optical_alert_event_id"], onu["onu_id"]


def test_get_unknown_alert_returns_404(real_client):
    headers, _ = _bootstrap_admin(real_client)
    r = real_client.get(f"{API}/optical-alerts/{uuid4()}", headers=headers)
    assert r.status_code == 404


def test_acknowledge_unknown_alert_returns_404(real_client):
    headers, _ = _bootstrap_admin(real_client)
    r = real_client.post(
        f"{API}/optical-alerts/{uuid4()}/acknowledge",
        headers=headers,
    )
    assert r.status_code == 404


def test_resolve_unknown_alert_returns_404(real_client):
    headers, _ = _bootstrap_admin(real_client)
    r = real_client.post(
        f"{API}/optical-alerts/{uuid4()}/resolve",
        headers=headers,
    )
    assert r.status_code == 404


def test_acknowledge_already_resolved_returns_400(real_client):
    _ensure_secret_env()
    headers, _ = _bootstrap_admin(real_client)
    inv = setup_inventory(real_client, headers)
    alert_id, _ = _generate_alert(real_client, headers, inv)

    # Resolve direto
    r1 = real_client.post(
        f"{API}/optical-alerts/{alert_id}/resolve",
        headers=headers,
    )
    assert r1.status_code == 200

    # Acknowledge depois de resolvido -> 400
    r2 = real_client.post(
        f"{API}/optical-alerts/{alert_id}/acknowledge",
        headers=headers,
    )
    assert r2.status_code == 400
    assert r2.json()["error"]["code"] == "bad_request"


def test_acknowledge_idempotent(real_client):
    _ensure_secret_env()
    headers, _ = _bootstrap_admin(real_client)
    inv = setup_inventory(real_client, headers)
    alert_id, _ = _generate_alert(real_client, headers, inv)

    r1 = real_client.post(
        f"{API}/optical-alerts/{alert_id}/acknowledge",
        headers=headers,
    )
    assert r1.status_code == 200
    assert r1.json()["status"] == "acknowledged"

    # Segundo acknowledge: idempotente, mesma resposta.
    r2 = real_client.post(
        f"{API}/optical-alerts/{alert_id}/acknowledge",
        headers=headers,
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "acknowledged"


def test_resolve_idempotent(real_client):
    _ensure_secret_env()
    headers, _ = _bootstrap_admin(real_client)
    inv = setup_inventory(real_client, headers)
    alert_id, _ = _generate_alert(real_client, headers, inv)

    r1 = real_client.post(
        f"{API}/optical-alerts/{alert_id}/resolve",
        headers=headers,
    )
    assert r1.status_code == 200

    r2 = real_client.post(
        f"{API}/optical-alerts/{alert_id}/resolve",
        headers=headers,
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "resolved"


def test_list_filter_by_olt_id(real_client):
    _ensure_secret_env()
    headers, _ = _bootstrap_admin(real_client)
    inv = setup_inventory(real_client, headers)
    _generate_alert(real_client, headers, inv)

    r = real_client.get(
        f"{API}/optical-alerts",
        headers=headers,
        params={"olt_id": str(inv["olt_id"])},
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 1


def test_list_filter_by_status(real_client):
    _ensure_secret_env()
    headers, _ = _bootstrap_admin(real_client)
    inv = setup_inventory(real_client, headers)
    alert_id, _ = _generate_alert(real_client, headers, inv)

    real_client.post(f"{API}/optical-alerts/{alert_id}/resolve", headers=headers)

    r_open = real_client.get(
        f"{API}/optical-alerts",
        headers=headers,
        params={"olt_id": str(inv["olt_id"]), "status": "open"},
    )
    assert r_open.status_code == 200
    # não deve mais ter open para essa ONU
    open_ids = [item["optical_alert_event_id"] for item in r_open.json()["items"]]
    assert alert_id not in open_ids

    r_resolved = real_client.get(
        f"{API}/optical-alerts",
        headers=headers,
        params={"olt_id": str(inv["olt_id"]), "status": "resolved"},
    )
    resolved_ids = [item["optical_alert_event_id"] for item in r_resolved.json()["items"]]
    assert alert_id in resolved_ids


def test_list_without_auth_returns_401(real_client):
    r = real_client.get(f"{API}/optical-alerts")
    assert r.status_code == 401
