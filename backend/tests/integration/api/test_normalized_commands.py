# Testes de integração das rotas /normalized-commands (M18a).

from __future__ import annotations

from uuid import uuid4

from tests.integration.api._provisioning_setup import setup_provisioning_catalog
from tests.integration.api.test_auth import _bootstrap_admin

API = "/api/v1"


def _payload(
    *,
    manufacturer_id,
    olt_model_id=None,
    command_key="authorize_onu",
    version_constraint=None,
    active=True,
) -> dict:
    return {
        "manufacturer_id": str(manufacturer_id),
        "olt_model_id": str(olt_model_id) if olt_model_id else None,
        "command_key": command_key,
        "command_type": "provision",
        "template_string": "auth onu serial {serial} index {onu_index}",
        "output_parser": "kv",
        "version_constraint": version_constraint,
        "timeout_ms": 15000,
        "requires_privileged": False,
        "supports_ssh": True,
        "supports_telnet": False,
        "active": active,
    }


# Happy paths
def test_create_command_with_olt_model(real_client):
    headers, _ = _bootstrap_admin(real_client)
    cat = setup_provisioning_catalog(real_client, headers)
    r = real_client.post(
        f"{API}/normalized-commands",
        headers=headers,
        json=_payload(
            manufacturer_id=cat["manufacturer_id"],
            olt_model_id=cat["olt_model_id"],
        ),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["command_key"] == "authorize_onu"
    assert body["command_type"] == "provision"
    assert body["timeout_ms"] == 15000


def test_create_command_without_olt_model(real_client):
    headers, _ = _bootstrap_admin(real_client)
    cat = setup_provisioning_catalog(real_client, headers)
    r = real_client.post(
        f"{API}/normalized-commands",
        headers=headers,
        json=_payload(manufacturer_id=cat["manufacturer_id"]),
    )
    assert r.status_code == 201, r.text
    assert r.json()["olt_model_id"] is None


# Validações cruzadas
def test_create_command_with_unknown_manufacturer_returns_400(real_client):
    headers, _ = _bootstrap_admin(real_client)
    r = real_client.post(
        f"{API}/normalized-commands",
        headers=headers,
        json=_payload(manufacturer_id=uuid4()),
    )
    assert r.status_code == 400, r.text


def test_create_command_with_mismatched_olt_model_returns_400(real_client):
    headers, _ = _bootstrap_admin(real_client)
    a = setup_provisioning_catalog(real_client, headers)
    b = setup_provisioning_catalog(real_client, headers)
    r = real_client.post(
        f"{API}/normalized-commands",
        headers=headers,
        json=_payload(
            manufacturer_id=a["manufacturer_id"],
            olt_model_id=b["olt_model_id"],
        ),
    )
    assert r.status_code == 400, r.text


# Unicidade parcial
def test_duplicate_active_command_returns_409(real_client):
    headers, _ = _bootstrap_admin(real_client)
    cat = setup_provisioning_catalog(real_client, headers)
    p = _payload(
        manufacturer_id=cat["manufacturer_id"],
        olt_model_id=cat["olt_model_id"],
    )
    r1 = real_client.post(f"{API}/normalized-commands", headers=headers, json=p)
    assert r1.status_code == 201, r1.text
    r2 = real_client.post(f"{API}/normalized-commands", headers=headers, json=p)
    assert r2.status_code == 409, r2.text


def test_paused_and_active_with_same_key_allowed(real_client):
    """Como o índice de unicidade é PARCIAL (WHERE active=TRUE), criar um
    inativo com a mesma chave de um ativo é permitido (versionamento)."""
    headers, _ = _bootstrap_admin(real_client)
    cat = setup_provisioning_catalog(real_client, headers)
    p_active = _payload(
        manufacturer_id=cat["manufacturer_id"],
        olt_model_id=cat["olt_model_id"],
        active=True,
    )
    r1 = real_client.post(f"{API}/normalized-commands", headers=headers, json=p_active)
    assert r1.status_code == 201, r1.text

    p_inactive = _payload(
        manufacturer_id=cat["manufacturer_id"],
        olt_model_id=cat["olt_model_id"],
        active=False,
    )
    r2 = real_client.post(f"{API}/normalized-commands", headers=headers, json=p_inactive)
    assert r2.status_code == 201, r2.text


def test_reactivating_collides_with_active(real_client):
    """PATCH active=True em comando inativo cuja chave já está ocupada
    por outro ativo deve retornar 409 (IntegrityError caught no service)."""
    headers, _ = _bootstrap_admin(real_client)
    cat = setup_provisioning_catalog(real_client, headers)

    r = real_client.post(
        f"{API}/normalized-commands",
        headers=headers,
        json=_payload(
            manufacturer_id=cat["manufacturer_id"],
            olt_model_id=cat["olt_model_id"],
            active=True,
        ),
    )
    assert r.status_code == 201
    # Cria inativo com mesma chave
    r2 = real_client.post(
        f"{API}/normalized-commands",
        headers=headers,
        json=_payload(
            manufacturer_id=cat["manufacturer_id"],
            olt_model_id=cat["olt_model_id"],
            active=False,
        ),
    )
    assert r2.status_code == 201
    inactive_id = r2.json()["normalized_command_id"]
    # Tenta reativar -> 409
    r3 = real_client.patch(
        f"{API}/normalized-commands/{inactive_id}",
        headers=headers,
        json={"active": True},
    )
    assert r3.status_code == 409, r3.text


# Filtros / listagem
def test_list_filter_by_command_key(real_client):
    headers, _ = _bootstrap_admin(real_client)
    cat = setup_provisioning_catalog(real_client, headers)
    for key in ("auth_a", "auth_b", "config_x"):
        real_client.post(
            f"{API}/normalized-commands",
            headers=headers,
            json=_payload(
                manufacturer_id=cat["manufacturer_id"],
                olt_model_id=cat["olt_model_id"],
                command_key=key,
            ),
        )
    r = real_client.get(
        f"{API}/normalized-commands",
        headers=headers,
        params={
            "manufacturer_id": str(cat["manufacturer_id"]),
            "command_key": "auth_a",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert all(item["command_key"] == "auth_a" for item in body["items"])
    assert body["total"] >= 1


# PATCH ordinário
def test_patch_template_string_succeeds(real_client):
    headers, _ = _bootstrap_admin(real_client)
    cat = setup_provisioning_catalog(real_client, headers)
    r = real_client.post(
        f"{API}/normalized-commands",
        headers=headers,
        json=_payload(manufacturer_id=cat["manufacturer_id"]),
    )
    cmd_id = r.json()["normalized_command_id"]
    r = real_client.patch(
        f"{API}/normalized-commands/{cmd_id}",
        headers=headers,
        json={"template_string": "novo template {serial}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["template_string"] == "novo template {serial}"


# Auth
def test_routes_require_admin(real_client):
    r = real_client.get(f"{API}/normalized-commands")
    assert r.status_code == 401, r.text
