# Testes de integração do ciclo signal_reading via Celery eager.

# Pre-requisito: PYTEST_OLT_SECRET no ambiente (conftest seta).

from __future__ import annotations

import os
from uuid import uuid4

from sqlalchemy import create_engine, text

from app.core.config import settings
from tests.integration.api._olt_mock import setup_inventory
from tests.integration.api._optical_mock import (
    clear_canned_optical_readings,
    create_onu_for_pon,
    set_canned_optical_readings,
)
from tests.integration.api.test_auth import _bootstrap_admin

API = "/api/v1"


def _sync_engine():
    return create_engine(settings.database.build_app_sync_url())


def _ensure_secret_env():
    os.environ.setdefault("PYTEST_OLT_SECRET", "pytest-fake-pass")


def _create_onu_model(real_client, headers, manufacturer_id):
    from uuid import uuid4 as _uuid

    r = real_client.post(
        f"{API}/onu-models",
        headers=headers,
        json={
            "manufacturer_id": str(manufacturer_id),
            "model": f"pytest-onum-{_uuid().hex[:8]}",
            "active": True,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["onu_model_id"]


# Happy path: leitura para 1 ONU viva, sem politicas, vira success.
def test_signal_reading_persists_optical_reading_for_known_onu(real_client):
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
    serial = onu["serial"]

    set_canned_optical_readings(
        inv["olt_id"],
        [
            {
                "serial": serial,
                "rx_power_dbm": -22.5,
                "tx_power_dbm": 2.0,
                "temperature": 45.0,
                "voltage": 3.3,
                "bias_current": 12.0,
                "distance_m": 3500.0,
                "status": "ok",
            }
        ],
    )

    try:
        r = real_client.post(
            f"{API}/collection-jobs/signal-reading",
            headers=headers,
            json={"olt_id": str(inv["olt_id"])},
        )
        assert r.status_code == 202, r.text
        body = r.json()
        assert body["status"] == "success"
        assert body["job_type"] == "signal_reading"

        # Lê histórico óptico
        r2 = real_client.get(
            f"{API}/onus/{onu['onu_id']}/optical-history",
            headers=headers,
        )
        assert r2.status_code == 200, r2.text
        items = r2.json()["items"]
        assert len(items) == 1
        assert items[0]["rx_power_dbm"] == -22.5
        assert items[0]["tx_power_dbm"] == 2.0
    finally:
        clear_canned_optical_readings(inv["olt_id"])


# Serial desconhecido -> descarte com log + PARTIAL
def test_signal_reading_partial_when_unknown_serial(real_client):
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
    set_canned_optical_readings(
        inv["olt_id"],
        [
            {
                "serial": onu["serial"],
                "rx_power_dbm": -22.0,
            },
            {
                # Serial não cadastrado
                "serial": "UNKN99999999",
                "rx_power_dbm": -20.0,
            },
        ],
    )
    try:
        r = real_client.post(
            f"{API}/collection-jobs/signal-reading",
            headers=headers,
            json={"olt_id": str(inv["olt_id"])},
        )
        assert r.status_code == 202, r.text
        assert r.json()["status"] == "partial"
    finally:
        clear_canned_optical_readings(inv["olt_id"])


# Violação gera alerta open.
def test_signal_reading_generates_alert_on_threshold_violation(real_client):
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

    # Cria policy global para rx_power_dbm: faixa [-30, -8]
    r_policy = real_client.post(
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
    assert r_policy.status_code == 201, r_policy.text

    # Leitura abaixo do mínimo: dispara alerta
    set_canned_optical_readings(
        inv["olt_id"],
        [
            {
                "serial": onu["serial"],
                "rx_power_dbm": -32.0,
            }
        ],
    )
    try:
        r = real_client.post(
            f"{API}/collection-jobs/signal-reading",
            headers=headers,
            json={"olt_id": str(inv["olt_id"])},
        )
        assert r.status_code == 202, r.text
        assert r.json()["status"] == "success"

        # Lista alertas open para a ONU
        r2 = real_client.get(
            f"{API}/optical-alerts",
            headers=headers,
            params={"onu_id": onu["onu_id"], "status": "open"},
        )
        assert r2.status_code == 200
        items = r2.json()["items"]
        assert len(items) == 1
        assert items[0]["metric_name"] == "rx_power_dbm"
        assert items[0]["value"] == -32.0
    finally:
        clear_canned_optical_readings(inv["olt_id"])


# Upsert logico de alerta: segunda violação na mesma métrica não duplica.
def test_repeated_violation_does_not_create_duplicate_alert(real_client):
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

    # Roda dois jobs em sequencia com violação
    for value in (-32.0, -33.5):
        set_canned_optical_readings(
            inv["olt_id"],
            [
                {
                    "serial": onu["serial"],
                    "rx_power_dbm": value,
                }
            ],
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

    r2 = real_client.get(
        f"{API}/optical-alerts",
        headers=headers,
        params={"onu_id": onu["onu_id"], "status": "open"},
    )
    items = r2.json()["items"]
    # UM único alerta open; value foi atualizado para o ultimo.
    assert len(items) == 1
    assert items[0]["value"] == -33.5


# Acknowledge + resolve.
def test_alert_acknowledge_then_resolve(real_client):
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
        real_client.post(
            f"{API}/collection-jobs/signal-reading",
            headers=headers,
            json={"olt_id": str(inv["olt_id"])},
        )
    finally:
        clear_canned_optical_readings(inv["olt_id"])

    r = real_client.get(
        f"{API}/optical-alerts",
        headers=headers,
        params={"onu_id": onu["onu_id"]},
    )
    alert_id = r.json()["items"][0]["optical_alert_event_id"]

    r_ack = real_client.post(
        f"{API}/optical-alerts/{alert_id}/acknowledge",
        headers=headers,
    )
    assert r_ack.status_code == 200
    assert r_ack.json()["status"] == "acknowledged"

    r_res = real_client.post(
        f"{API}/optical-alerts/{alert_id}/resolve",
        headers=headers,
    )
    assert r_res.status_code == 200
    assert r_res.json()["status"] == "resolved"
    assert r_res.json()["resolved_at"] is not None


# OLT inexistente -> 400
def test_signal_reading_unknown_olt_returns_400(real_client):
    _ensure_secret_env()
    headers, _ = _bootstrap_admin(real_client)
    r = real_client.post(
        f"{API}/collection-jobs/signal-reading",
        headers=headers,
        json={"olt_id": str(uuid4())},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "bad_request"


# Sem token -> 401
def test_signal_reading_without_auth_returns_401(real_client):
    r = real_client.post(
        f"{API}/collection-jobs/signal-reading",
        json={"olt_id": str(uuid4())},
    )
    assert r.status_code == 401


# Atualiza last_signal_at em onu_runtime_state (A3)
def test_signal_reading_updates_runtime_state_last_signal(real_client):
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

    engine = _sync_engine()
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT last_signal_at, last_collected_at
                    FROM onu_runtime_state
                    WHERE onu_id = :id
                    """
                ),
                {"id": onu["onu_id"]},
            ).first()
        assert row is not None
        assert row[0] is not None, "last_signal_at deveria estar preenchido"
        assert row[1] is not None, "last_collected_at deveria estar preenchido"
    finally:
        engine.dispose()
