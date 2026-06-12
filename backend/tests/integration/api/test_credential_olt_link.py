# credencial vinculada a OLT viva NÃO pode ser desativada via PATCH em
# /credentials/{id} (409). Após soft delete da OLT, a desativação passa.

# Em arquivo próprio para não tocar test_credentials.py.

from __future__ import annotations

import uuid
from typing import Any

API = "/api/v1"

_ip_counter = 0


def _unique_ip() -> str:
    global _ip_counter
    _ip_counter += 1
    a = (_ip_counter // 256) % 256
    b = _ip_counter % 256
    return f"10.88.{a}.{b}"


def _suffix() -> str:
    return uuid.uuid4().hex[:8]


def _error_code(resp: Any) -> str | None:
    try:
        body = resp.json()
    except Exception:
        return None
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict) and "code" in err:
            return err["code"]
        if "code" in body:
            return body["code"]
        detail = body.get("detail")
        if isinstance(detail, dict) and "code" in detail:
            return detail["code"]
    return None


# Helpers de pré-requisito (AJUSTAR se o contrato real divergir)
def _create_manufacturer(client) -> str:
    r = client.post(
        f"{API}/manufacturers",
        json={"name": f"pytest-mfr-{_suffix()}", "slug": f"pytest-{_suffix()}", "active": True},
    )
    assert r.status_code == 201, f"setup manufacturer falhou: {r.status_code} {r.text}"
    return r.json()["manufacturer_id"]


def _create_olt_model(client, manufacturer_id: str) -> str:
    r = client.post(
        f"{API}/olt-models",
        json={"manufacturer_id": manufacturer_id, "model": f"pytest-model-{_suffix()}"},
    )
    assert r.status_code == 201, f"setup olt_model falhou: {r.status_code} {r.text}"
    return r.json()["olt_model_id"]


def _create_credential(client) -> str:
    r = client.post(
        f"{API}/credentials",
        json={
            "label": f"pytest-cred-{_suffix()}",
            "username": "admin",
            "secret_ref": "OLT_LAB_PASSWORD",
            "auth_type": "password",
            "active": True,
        },
    )
    assert r.status_code == 201, f"setup credential falhou: {r.status_code} {r.text}"
    return r.json()["credential_id"]


def _create_olt(client, olt_model_id: str, credential_id: str) -> str:
    r = client.post(
        f"{API}/olts",
        json={
            "name": f"pytest-olt-{_suffix()}",
            "ip": _unique_ip(),
            "management_port": 22,
            "olt_model_id": olt_model_id,
            "credential_id": credential_id,
        },
    )
    assert r.status_code == 201, f"setup olt falhou: {r.status_code} {r.text}"
    return r.json()["olt_id"]


# Regressão
def test_cannot_deactivate_credential_in_use(real_client):
    mfr = _create_manufacturer(real_client)
    model = _create_olt_model(real_client, mfr)
    cred = _create_credential(real_client)
    _create_olt(real_client, model, cred)

    # Credencial em uso por OLT viva: desativar deve dar 409.
    r = real_client.patch(f"{API}/credentials/{cred}", json={"active": False})
    assert r.status_code == 409, r.text
    assert _error_code(r) == "conflict"


def test_can_deactivate_credential_after_olt_soft_deleted(real_client):
    mfr = _create_manufacturer(real_client)
    model = _create_olt_model(real_client, mfr)
    cred = _create_credential(real_client)
    olt_id = _create_olt(real_client, model, cred)

    # Soft delete da OLT libera a credencial.
    assert real_client.delete(f"{API}/olts/{olt_id}").status_code == 204

    r = real_client.patch(f"{API}/credentials/{cred}", json={"active": False})
    assert r.status_code == 200, r.text
    assert r.json()["active"] is False


def test_other_credential_fields_still_patchable_while_in_use(real_client):
    # Garante que o bloqueio é SÓ para active=false. Outras edições passam mesmo com OLT viva vinculada.
    mfr = _create_manufacturer(real_client)
    model = _create_olt_model(real_client, mfr)
    cred = _create_credential(real_client)
    _create_olt(real_client, model, cred)

    r = real_client.patch(f"{API}/credentials/{cred}", json={"secret_ref": "OLT_LAB_PASSWORD_V2"})
    assert r.status_code == 200, r.text
