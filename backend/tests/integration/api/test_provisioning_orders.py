# Testes de integração das rotas /provisioning-orders.

# Modo eager do Celery (setado em conftest): task_always_eager=True faz
# .delay() rodar SÍNCRONO. Sob eager, ao retornar do POST, a ordem já
# está em estado terminal.

from __future__ import annotations

import os
from uuid import uuid4

from sqlalchemy import create_engine, text  # noqa: F401

from app.core.config import settings
from tests.integration.api._olt_mock import (
    clear_canned_provisioning,
    set_canned_provisioning,
)
from tests.integration.api._provisioning_setup import (
    build_snapshot,
    seed_pending_onu,
    setup_full_provisioning_chain,
)
from tests.integration.api.test_auth import _bootstrap_admin

API = "/api/v1"


def _sync_engine():
    return create_engine(settings.database.build_app_sync_url())


def _ensure_secret_env() -> None:
    os.environ.setdefault("PYTEST_OLT_SECRET", "pytest-fake-pass")


def _unique_key() -> str:
    return f"pytest-idem-{uuid4().hex[:12]}"


# Happy path: POST cria ordem, worker roda eager e retorna SUCCESS
def test_create_order_success_with_default_canned(real_client):
    _ensure_secret_env()
    headers, _ = _bootstrap_admin(real_client)
    chain = setup_full_provisioning_chain(real_client, headers)

    # Serial reconhecido via pending_onu ativo
    serial = "PYTS00000001"
    engine = _sync_engine()
    try:
        seed_pending_onu(engine, chain, serial=serial, state="detected")
    finally:
        engine.dispose()

    body = {
        "olt_id": str(chain["olt_id"]),
        "pon_port_id": str(chain["pon_port_id"]),
        "serial": serial,
        "provisioning_template_id": str(chain["provisioning_template_id"]),
        "idempotency_key": _unique_key(),
        "snapshot": build_snapshot(chain),
    }
    r = real_client.post(f"{API}/provisioning-orders", headers=headers, json=body)
    assert r.status_code == 202, r.text
    out = r.json()
    # Default do mock: sucesso silencioso
    assert out["status"] == "success"
    assert out["onu_id"] is None  # serial ainda em pending, não materializado
    assert out["snapshot_params"]["serial"] == serial
    assert out["snapshot_params"]["vlan_number"] == chain["vlan_number"]
    assert out["snapshot_params"]["line_profile_name"]
    assert out["snapshot_params"]["service_profile_name"]
    assert len(out["steps"]) >= 1
    assert out["rollback"] is None


# POST com canned FAILED: sem rollback (template com 1 step) vira FAILED
def test_create_order_failed_when_canned_step_fails(real_client):
    _ensure_secret_env()
    headers, _ = _bootstrap_admin(real_client)
    chain = setup_full_provisioning_chain(real_client, headers)

    serial = "PYTS00000002"
    engine = _sync_engine()
    try:
        seed_pending_onu(engine, chain, serial=serial)
    finally:
        engine.dispose()

    # Injeta canned failed no adapter mock (StepResult com success=False)
    set_canned_provisioning(
        chain["olt_id"],
        steps=[
            {
                "command_sent": "echo pytest-authorize_onu",
                "output_received": "ERROR: fake failure",
                "success": False,
                "duration_ms": 12,
            }
        ],
        overall_success=False,
    )
    try:
        body = {
            "olt_id": str(chain["olt_id"]),
            "pon_port_id": str(chain["pon_port_id"]),
            "serial": serial,
            "provisioning_template_id": str(chain["provisioning_template_id"]),
            "idempotency_key": _unique_key(),
            "snapshot": build_snapshot(chain),
        }
        r = real_client.post(f"{API}/provisioning-orders", headers=headers, json=body)
        assert r.status_code == 202, r.text
        out = r.json()
        # Status terminal: failed (sem rollback porque não há step bem-sucedido para reverter)
        assert out["status"] in ("failed", "rolled_back", "partial")
        assert len(out["steps"]) >= 1
    finally:
        clear_canned_provisioning(chain["olt_id"])


# 409 idempotency: segunda POST com mesma key
def test_duplicate_idempotency_key_returns_409(real_client):
    _ensure_secret_env()
    headers, _ = _bootstrap_admin(real_client)
    chain = setup_full_provisioning_chain(real_client, headers)

    serial = "PYTS00000003"
    engine = _sync_engine()
    try:
        seed_pending_onu(engine, chain, serial=serial)
    finally:
        engine.dispose()

    idem = _unique_key()
    body = {
        "olt_id": str(chain["olt_id"]),
        "pon_port_id": str(chain["pon_port_id"]),
        "serial": serial,
        "provisioning_template_id": str(chain["provisioning_template_id"]),
        "idempotency_key": idem,
        "snapshot": build_snapshot(chain),
    }
    r1 = real_client.post(f"{API}/provisioning-orders", headers=headers, json=body)
    assert r1.status_code == 202, r1.text

    # Segundo POST com MESMA idempotency_key -> 409
    body2 = dict(body)
    body2["snapshot"] = build_snapshot(chain)  # snapshot diferente, key igual
    r2 = real_client.post(f"{API}/provisioning-orders", headers=headers, json=body2)
    assert r2.status_code == 409, r2.text
    assert r2.json()["error"]["code"] == "conflict"


# 400: serial não reconhecido
def test_unknown_serial_returns_400(real_client):
    _ensure_secret_env()
    headers, _ = _bootstrap_admin(real_client)
    chain = setup_full_provisioning_chain(real_client, headers)

    body = {
        "olt_id": str(chain["olt_id"]),
        "pon_port_id": str(chain["pon_port_id"]),
        "serial": "NOTFOUND0001",
        "provisioning_template_id": str(chain["provisioning_template_id"]),
        "idempotency_key": _unique_key(),
        "snapshot": build_snapshot(chain),
    }
    r = real_client.post(f"{API}/provisioning-orders", headers=headers, json=body)
    assert r.status_code == 400, r.text
    assert r.json()["error"]["code"] == "bad_request"


# 400: pon_port de outra OLT
def test_pon_port_from_different_olt_returns_400(real_client):
    _ensure_secret_env()
    headers, _ = _bootstrap_admin(real_client)
    chain_a = setup_full_provisioning_chain(real_client, headers)
    chain_b = setup_full_provisioning_chain(real_client, headers)

    body = {
        "olt_id": str(chain_a["olt_id"]),
        "pon_port_id": str(chain_b["pon_port_id"]),  # PON de outra OLT
        "serial": "PYTS00000004",
        "provisioning_template_id": str(chain_a["provisioning_template_id"]),
        "idempotency_key": _unique_key(),
        "snapshot": build_snapshot(chain_a),
    }
    r = real_client.post(f"{API}/provisioning-orders", headers=headers, json=body)
    assert r.status_code == 400, r.text
    assert r.json()["error"]["code"] == "bad_request"


# 400: line_profile de outra OLT
def test_line_profile_from_different_olt_returns_400(real_client):
    _ensure_secret_env()
    headers, _ = _bootstrap_admin(real_client)
    chain_a = setup_full_provisioning_chain(real_client, headers)
    chain_b = setup_full_provisioning_chain(real_client, headers)

    serial = "PYTS00000005"
    engine = _sync_engine()
    try:
        seed_pending_onu(engine, chain_a, serial=serial)
    finally:
        engine.dispose()

    snap = build_snapshot(chain_a)
    snap["line_profile_id"] = chain_b["line_profile_id"]  # profile da OLT B
    body = {
        "olt_id": str(chain_a["olt_id"]),
        "pon_port_id": str(chain_a["pon_port_id"]),
        "serial": serial,
        "provisioning_template_id": str(chain_a["provisioning_template_id"]),
        "idempotency_key": _unique_key(),
        "snapshot": snap,
    }
    r = real_client.post(f"{API}/provisioning-orders", headers=headers, json=body)
    assert r.status_code == 400, r.text


# 400: retry_of_order_id inexistente
def test_retry_of_unknown_order_returns_400(real_client):
    _ensure_secret_env()
    headers, _ = _bootstrap_admin(real_client)
    chain = setup_full_provisioning_chain(real_client, headers)

    serial = "PYTS00000006"
    engine = _sync_engine()
    try:
        seed_pending_onu(engine, chain, serial=serial)
    finally:
        engine.dispose()

    body = {
        "olt_id": str(chain["olt_id"]),
        "pon_port_id": str(chain["pon_port_id"]),
        "serial": serial,
        "provisioning_template_id": str(chain["provisioning_template_id"]),
        "idempotency_key": _unique_key(),
        "retry_of_order_id": str(uuid4()),  # inexistente
        "snapshot": build_snapshot(chain),
    }
    r = real_client.post(f"{API}/provisioning-orders", headers=headers, json=body)
    assert r.status_code == 400, r.text


# 400: template inativo----
def test_inactive_template_returns_400(real_client):
    _ensure_secret_env()
    headers, _ = _bootstrap_admin(real_client)
    chain = setup_full_provisioning_chain(real_client, headers)

    # Desativa o template via PATCH
    r = real_client.patch(
        f"{API}/provisioning-templates/{chain['provisioning_template_id']}",
        headers=headers,
        json={"active": False},
    )
    assert r.status_code == 200, r.text

    serial = "PYTS00000007"
    engine = _sync_engine()
    try:
        seed_pending_onu(engine, chain, serial=serial)
    finally:
        engine.dispose()

    body = {
        "olt_id": str(chain["olt_id"]),
        "pon_port_id": str(chain["pon_port_id"]),
        "serial": serial,
        "provisioning_template_id": str(chain["provisioning_template_id"]),
        "idempotency_key": _unique_key(),
        "snapshot": build_snapshot(chain),
    }
    r = real_client.post(f"{API}/provisioning-orders", headers=headers, json=body)
    assert r.status_code == 400, r.text


# Sem token -> 401
def test_create_without_auth_returns_401(real_client):
    r = real_client.post(f"{API}/provisioning-orders", json={"olt_id": str(uuid4())})
    assert r.status_code == 401


# Detail inexistente -> 404
def test_get_unknown_order_returns_404(real_client):
    headers, _ = _bootstrap_admin(real_client)
    r = real_client.get(f"{API}/provisioning-orders/{uuid4()}", headers=headers)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


# Listagem paginada com filtros
def test_list_orders_with_filters_and_pagination(real_client):
    _ensure_secret_env()
    headers, _ = _bootstrap_admin(real_client)
    chain = setup_full_provisioning_chain(real_client, headers)

    engine = _sync_engine()
    try:
        # cria 2 ordens de sucesso
        for i in range(2):
            serial = f"PYTL0000000{i}"
            seed_pending_onu(engine, chain, serial=serial)
            body = {
                "olt_id": str(chain["olt_id"]),
                "pon_port_id": str(chain["pon_port_id"]),
                "serial": serial,
                "provisioning_template_id": str(chain["provisioning_template_id"]),
                "idempotency_key": _unique_key(),
                "snapshot": build_snapshot(chain, custom_id=f"c{i}"),
            }
            r = real_client.post(f"{API}/provisioning-orders", headers=headers, json=body)
            assert r.status_code == 202, r.text
    finally:
        engine.dispose()

    r = real_client.get(
        f"{API}/provisioning-orders",
        headers=headers,
        params={"olt_id": str(chain["olt_id"])},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 2
    assert body["page"] == 1
    assert body["page_size"] == 50

    # ordem desc por created_at
    times = [item["created_at"] for item in body["items"]]
    assert times == sorted(times, reverse=True)

    # filtro por status=success
    r2 = real_client.get(
        f"{API}/provisioning-orders",
        headers=headers,
        params={"olt_id": str(chain["olt_id"]), "status": "success"},
    )
    assert r2.status_code == 200
    for item in r2.json()["items"]:
        assert item["status"] == "success"


# payload malformado -> 422
def test_malformed_payload_returns_422(real_client):
    _ensure_secret_env()
    headers, _ = _bootstrap_admin(real_client)
    r = real_client.post(
        f"{API}/provisioning-orders",
        headers=headers,
        json={"olt_id": str(uuid4())},  # faltando obrigatórios
    )
    assert r.status_code == 422, r.text


# snapshot extra field -> 422 (extra=forbid)
def test_snapshot_extra_field_returns_422(real_client):
    _ensure_secret_env()
    headers, _ = _bootstrap_admin(real_client)
    chain = setup_full_provisioning_chain(real_client, headers)

    snap = build_snapshot(chain)
    snap["random_field"] = "not-allowed"
    body = {
        "olt_id": str(chain["olt_id"]),
        "pon_port_id": str(chain["pon_port_id"]),
        "serial": "PYTS00000010",
        "provisioning_template_id": str(chain["provisioning_template_id"]),
        "idempotency_key": _unique_key(),
        "snapshot": snap,
    }
    r = real_client.post(f"{API}/provisioning-orders", headers=headers, json=body)
    assert r.status_code == 422, r.text
