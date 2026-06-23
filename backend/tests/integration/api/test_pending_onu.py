# Testes de integração das rotas /pending-onus.

# Como pending_onu é populado via worker, os testes que exigem dados
# semeiam diretamente no banco para isolar a rota da maquinaria de
# Celery+adapter. O fluxo end-to-end já é coberto por test_collection_jobs.py.

from __future__ import annotations

import os
from uuid import uuid4

from sqlalchemy import create_engine, text

from app.core.config import settings
from tests.integration.api._olt_mock import setup_inventory
from tests.integration.api.test_auth import _bootstrap_admin

API = "/api/v1"


def _sync_engine():
    return create_engine(settings.database.build_app_sync_url())


def _seed_pending(olt_id, pon_port_id, serial, state="detected"):
    engine = _sync_engine()
    try:
        with engine.connect() as conn, conn.begin():
            conn.execute(
                text(
                    """
                    INSERT INTO pending_onu (
                        olt_id, pon_port_id, serial, state,
                        first_seen_at, last_seen_at, discovery_source
                    ) VALUES (
                        :olt, :pon, :serial,
                        CAST(:state AS pending_onu_state_enum),
                        NOW(), NOW(), 'pytest-seed'
                    )
                    ON CONFLICT (olt_id, pon_port_id, serial) DO NOTHING
                    """
                ),
                {
                    "olt": str(olt_id),
                    "pon": str(pon_port_id),
                    "serial": serial,
                    "state": state,
                },
            )
    finally:
        engine.dispose()


def test_list_without_auth_returns_401(real_client):
    r = real_client.get(f"{API}/pending-onus")
    assert r.status_code == 401


def test_list_default_pagination(real_client):
    os.environ.setdefault("PYTEST_OLT_SECRET", "pytest-fake-pass")
    headers, _ = _bootstrap_admin(real_client)
    inv = setup_inventory(real_client, headers)
    _seed_pending(inv["olt_id"], inv["pon_port_id"], "AAAA00000001")
    _seed_pending(inv["olt_id"], inv["pon_port_id"], "BBBB00000002")

    r = real_client.get(
        f"{API}/pending-onus",
        headers=headers,
        params={"olt_id": str(inv["olt_id"])},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 2
    assert body["page"] == 1
    assert body["page_size"] == 50


def test_list_filter_by_state(real_client):
    os.environ.setdefault("PYTEST_OLT_SECRET", "pytest-fake-pass")
    headers, _ = _bootstrap_admin(real_client)
    inv = setup_inventory(real_client, headers)
    _seed_pending(inv["olt_id"], inv["pon_port_id"], "CCCC00000001", state="detected")
    _seed_pending(inv["olt_id"], inv["pon_port_id"], "DDDD00000002", state="resolved")

    r = real_client.get(
        f"{API}/pending-onus",
        headers=headers,
        params={"olt_id": str(inv["olt_id"]), "state": "resolved"},
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert all(item["state"] == "resolved" for item in items)
    serials = [item["serial"] for item in items]
    assert "DDDD00000002" in serials
    assert "CCCC00000001" not in serials


def test_list_filter_by_pon_port(real_client):
    os.environ.setdefault("PYTEST_OLT_SECRET", "pytest-fake-pass")
    headers, _ = _bootstrap_admin(real_client)
    inv = setup_inventory(real_client, headers)
    _seed_pending(inv["olt_id"], inv["pon_port_id"], "EEEE00000001")

    r = real_client.get(
        f"{API}/pending-onus",
        headers=headers,
        params={"pon_port_id": str(inv["pon_port_id"])},
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert all(item["pon_port_id"] == str(inv["pon_port_id"]) for item in items)


def test_get_detail(real_client):
    os.environ.setdefault("PYTEST_OLT_SECRET", "pytest-fake-pass")
    headers, _ = _bootstrap_admin(real_client)
    inv = setup_inventory(real_client, headers)
    _seed_pending(inv["olt_id"], inv["pon_port_id"], "FFFF00000001")

    r = real_client.get(
        f"{API}/pending-onus",
        headers=headers,
        params={"olt_id": str(inv["olt_id"])},
    )
    pending_id = next(
        item["pending_onu_id"] for item in r.json()["items"] if item["serial"] == "FFFF00000001"
    )

    r2 = real_client.get(f"{API}/pending-onus/{pending_id}", headers=headers)
    assert r2.status_code == 200
    assert r2.json()["serial"] == "FFFF00000001"


def test_get_unknown_returns_404(real_client):
    headers, _ = _bootstrap_admin(real_client)
    r = real_client.get(f"{API}/pending-onus/{uuid4()}", headers=headers)
    assert r.status_code == 404
