# Testes de integração de GET /onus/{id}/optical-history.

from __future__ import annotations

import os
from uuid import uuid4

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


def _populate_one_reading(real_client, headers, inv, onu):
    set_canned_optical_readings(
        inv["olt_id"],
        [{"serial": onu["serial"], "rx_power_dbm": -22.0}],
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


def test_history_returns_empty_when_no_readings(real_client):
    _ensure_secret_env()
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
        f"{API}/onus/{onu['onu_id']}/optical-history",
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 0
    assert body["items"] == []


def test_history_returns_recent_reading(real_client):
    _ensure_secret_env()
    headers, _ = _bootstrap_admin(real_client)
    inv = setup_inventory(real_client, headers)
    onu_model_id = _create_onu_model(real_client, headers, inv["manufacturer_id"])
    onu = create_onu_for_pon(
        real_client,
        headers,
        pon_port_id=inv["pon_port_id"],
        onu_model_id=onu_model_id,
    )
    _populate_one_reading(real_client, headers, inv, onu)

    r = real_client.get(
        f"{API}/onus/{onu['onu_id']}/optical-history",
        headers=headers,
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["rx_power_dbm"] == -22.0


def test_history_unknown_onu_returns_404(real_client):
    headers, _ = _bootstrap_admin(real_client)
    r = real_client.get(
        f"{API}/onus/{uuid4()}/optical-history",
        headers=headers,
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_history_without_auth_returns_401(real_client):
    r = real_client.get(f"{API}/onus/{uuid4()}/optical-history")
    assert r.status_code == 401


def test_history_respects_pagination(real_client):
    _ensure_secret_env()
    headers, _ = _bootstrap_admin(real_client)
    inv = setup_inventory(real_client, headers)
    onu_model_id = _create_onu_model(real_client, headers, inv["manufacturer_id"])
    onu = create_onu_for_pon(
        real_client,
        headers,
        pon_port_id=inv["pon_port_id"],
        onu_model_id=onu_model_id,
    )
    # 3 leituras em jobs sequenciais
    for value in (-20.0, -21.0, -22.0):
        set_canned_optical_readings(
            inv["olt_id"],
            [{"serial": onu["serial"], "rx_power_dbm": value}],
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

    r = real_client.get(
        f"{API}/onus/{onu['onu_id']}/optical-history",
        headers=headers,
        params={"page": 1, "page_size": 2},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert len(body["items"]) == 2
    assert body["has_next"] is True
    assert body["has_prev"] is False
