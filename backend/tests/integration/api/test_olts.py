# Testes de integração da OLT (usam a app real + Postgres via `real_client`).

from __future__ import annotations

import uuid
from typing import Any

import pytest

API = "/api/v1"

# Contador de IPs para evitar colisão de (ip, porta) entre testes.
_ip_counter = 0


def _unique_ip() -> str:
    global _ip_counter
    _ip_counter += 1
    a = (_ip_counter // 256) % 256
    b = _ip_counter % 256
    return f"10.77.{a}.{b}"


def _suffix() -> str:
    return uuid.uuid4().hex[:8]


def _error_code(resp: Any) -> str | None:
    """Extrai o código de erro de domínio, tolerando formatos de envelope.
    Tenta {"error": {"code": ...}}, depois {"code": ...}, depois {"detail": ...}."""
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
    payload = {
        "name": f"pytest-mfr-{_suffix()}",
        "slug": f"pytest-{_suffix()}",
        "active": True,
    }
    r = client.post(f"{API}/manufacturers", json=payload)
    assert r.status_code == 201, f"setup manufacturer falhou: {r.status_code} {r.text}"
    return r.json()["manufacturer_id"]


def _create_olt_model(client, manufacturer_id: str) -> str:
    # PREMISSA: olt_model exige manufacturer_id + model. Se houver mais campos
    # obrigatórios (ex.: contagem de PONs/uplinks), adicione aqui.
    payload = {
        "manufacturer_id": manufacturer_id,
        "model": f"pytest-model-{_suffix()}",
    }
    r = client.post(f"{API}/olt_models", json=payload)
    assert r.status_code == 201, f"setup olt_model falhou: {r.status_code} {r.text}"
    return r.json()["olt_model_id"]


def _create_credential(client, *, active: bool = True) -> str:
    payload = {
        "label": f"pytest-cred-{_suffix()}",
        "username": "admin",
        "secret_ref": "OLT_LAB_PASSWORD",
        "auth_type": "password",
        "active": True,
    }
    r = client.post(f"{API}/credentials", json=payload)
    assert r.status_code == 201, f"setup credential falhou: {r.status_code} {r.text}"
    cred_id = r.json()["credential_id"]
    if not active:
        r2 = client.patch(f"{API}/credentials/{cred_id}", json={"active": False})
        assert r2.status_code == 200, f"setup deactivate falhou: {r2.status_code} {r2.text}"
    return cred_id


@pytest.fixture(scope="module")
def prereqs(real_client) -> dict[str, str]:
    """Cria manufacturer + olt_model + credencial ativa + credencial inativa,
    reaproveitados pelos testes do módulo."""
    mfr = _create_manufacturer(real_client)
    return {
        "manufacturer_id": mfr,
        "olt_model_id": _create_olt_model(real_client, mfr),
        "credential_id": _create_credential(real_client, active=True),
        "inactive_credential_id": _create_credential(real_client, active=False),
    }


def _olt_payload(prereqs: dict[str, str], **overrides) -> dict:
    base = {
        "name": f"pytest-olt-{_suffix()}",
        "ip": _unique_ip(),
        "management_port": 22,
        "credential_id": prereqs["credential_id"],
        "olt_model_id": prereqs["olt_model_id"],
    }
    base.update(overrides)
    return base


# Happy path
def test_create_olt_returns_201_with_defaults(real_client, prereqs):
    r = real_client.post(f"{API}/olts", json=_olt_payload(prereqs))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["connection_status"] == "unknown"  # server_default via RETURNING
    assert body["access_protocol"] == "ssh"
    assert body["timezone"] == "UTC"
    assert body["polling_enabled"] is True
    assert body["active"] is True
    assert "olt_id" in body
    assert "deleted_at" not in body  # D11.2


def test_get_olt_detail(real_client, prereqs):
    created = real_client.post(f"{API}/olts", json=_olt_payload(prereqs)).json()
    r = real_client.get(f"{API}/olts/{created['olt_id']}")
    assert r.status_code == 200
    assert r.json()["olt_id"] == created["olt_id"]


def test_list_contains_created(real_client, prereqs):
    created = real_client.post(f"{API}/olts", json=_olt_payload(prereqs)).json()
    r = real_client.get(f"{API}/olts", params={"search": created["name"]})
    assert r.status_code == 200
    ids = [item["olt_id"] for item in r.json()["items"]]
    assert created["olt_id"] in ids


# Conflitos de unicidade
def test_duplicate_name_conflicts(real_client, prereqs):
    p1 = _olt_payload(prereqs)
    assert real_client.post(f"{API}/olts", json=p1).status_code == 201
    # mesmo name, ip diferente
    p2 = _olt_payload(prereqs, name=p1["name"])
    r = real_client.post(f"{API}/olts", json=p2)
    assert r.status_code == 409
    assert _error_code(r) == "conflict"


def test_duplicate_ip_port_conflicts(real_client, prereqs):
    p1 = _olt_payload(prereqs)
    assert real_client.post(f"{API}/olts", json=p1).status_code == 201
    # mesmo ip+porta, name diferente
    p2 = _olt_payload(prereqs, ip=p1["ip"], management_port=p1["management_port"])
    r = real_client.post(f"{API}/olts", json=p2)
    assert r.status_code == 409
    assert _error_code(r) == "conflict"


def test_same_ip_different_port_is_allowed(real_client, prereqs):
    p1 = _olt_payload(prereqs, management_port=22)
    assert real_client.post(f"{API}/olts", json=p1).status_code == 201
    p2 = _olt_payload(prereqs, ip=p1["ip"], management_port=23)
    r = real_client.post(f"{API}/olts", json=p2)
    assert r.status_code == 201, r.text


# Validação de FK
def test_invalid_olt_model_returns_400(real_client, prereqs):
    p = _olt_payload(prereqs, olt_model_id=str(uuid.uuid4()))
    r = real_client.post(f"{API}/olts", json=p)
    assert r.status_code == 400, r.text
    assert _error_code(r) == "bad_request"


def test_invalid_credential_returns_400(real_client, prereqs):
    p = _olt_payload(prereqs, credential_id=str(uuid.uuid4()))
    r = real_client.post(f"{API}/olts", json=p)
    assert r.status_code == 400, r.text
    assert _error_code(r) == "bad_request"


def test_inactive_credential_returns_400(real_client, prereqs):
    p = _olt_payload(prereqs, credential_id=prereqs["inactive_credential_id"])
    r = real_client.post(f"{API}/olts", json=p)
    assert r.status_code == 400, r.text
    assert _error_code(r) == "bad_request"


# PATCH
def test_patch_name(real_client, prereqs):
    created = real_client.post(f"{API}/olts", json=_olt_payload(prereqs)).json()
    novo = f"pytest-olt-{_suffix()}"
    r = real_client.patch(f"{API}/olts/{created['olt_id']}", json={"name": novo})
    assert r.status_code == 200
    assert r.json()["name"] == novo


def test_patch_active_false_keeps_pair_locked(real_client, prereqs):
    # Pausa administrativa NÃO libera o par. Outra OLT com mesmo ip+porta deve continuar conflitando.
    p1 = _olt_payload(prereqs)
    created = real_client.post(f"{API}/olts", json=p1).json()
    r = real_client.patch(f"{API}/olts/{created['olt_id']}", json={"active": False})
    assert r.status_code == 200
    assert r.json()["active"] is False

    p2 = _olt_payload(prereqs, ip=p1["ip"], management_port=p1["management_port"])
    r2 = real_client.post(f"{API}/olts", json=p2)
    assert r2.status_code == 409


def test_patch_invalid_credential_returns_400(real_client, prereqs):
    created = real_client.post(f"{API}/olts", json=_olt_payload(prereqs)).json()
    r = real_client.patch(
        f"{API}/olts/{created['olt_id']}",
        json={"credential_id": str(uuid.uuid4())},
    )
    assert r.status_code == 400


def test_patch_nonexistent_returns_404(real_client):
    r = real_client.patch(f"{API}/olts/{uuid.uuid4()}", json={"name": "pytest-x"})
    assert r.status_code == 404


# Soft delete
def test_soft_delete_returns_204_then_404(real_client, prereqs):
    created = real_client.post(f"{API}/olts", json=_olt_payload(prereqs)).json()
    r = real_client.delete(f"{API}/olts/{created['olt_id']}")
    assert r.status_code == 204
    assert r.content == b""  # corpo vazio
    # após deletar, detalhe -> 404
    assert real_client.get(f"{API}/olts/{created['olt_id']}").status_code == 404


def test_soft_delete_frees_name(real_client, prereqs):
    p1 = _olt_payload(prereqs)
    created = real_client.post(f"{API}/olts", json=p1).json()
    real_client.delete(f"{API}/olts/{created['olt_id']}")
    # mesmo name agora deve ser aceito (unicidade parcial liberou)
    p2 = _olt_payload(prereqs, name=p1["name"])
    r = real_client.post(f"{API}/olts", json=p2)
    assert r.status_code == 201, r.text


def test_soft_delete_frees_ip_port(real_client, prereqs):
    p1 = _olt_payload(prereqs)
    created = real_client.post(f"{API}/olts", json=p1).json()
    real_client.delete(f"{API}/olts/{created['olt_id']}")
    p2 = _olt_payload(prereqs, ip=p1["ip"], management_port=p1["management_port"])
    r = real_client.post(f"{API}/olts", json=p2)
    assert r.status_code == 201, r.text


def test_delete_nonexistent_returns_404(real_client):
    r = real_client.delete(f"{API}/olts/{uuid.uuid4()}")
    assert r.status_code == 404


def test_double_delete_returns_404(real_client, prereqs):
    created = real_client.post(f"{API}/olts", json=_olt_payload(prereqs)).json()
    assert real_client.delete(f"{API}/olts/{created['olt_id']}").status_code == 204
    assert real_client.delete(f"{API}/olts/{created['olt_id']}").status_code == 404
