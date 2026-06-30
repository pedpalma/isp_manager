# Testes de integração das rotas /provisioning-templates (M18a).

from __future__ import annotations

from uuid import uuid4

from tests.integration.api._provisioning_setup import (
    make_raw_template,
    setup_provisioning_catalog,
)
from tests.integration.api.test_auth import _bootstrap_admin

API = "/api/v1"


# Happy paths
def test_create_template_with_olt_model_success(real_client):
    headers, _ = _bootstrap_admin(real_client)
    cat = setup_provisioning_catalog(real_client, headers)

    payload = {
        "manufacturer_id": str(cat["manufacturer_id"]),
        "olt_model_id": str(cat["olt_model_id"]),
        "template_scope": "onu_provision",
        "name": "pytest-tpl-default",
        "version": "1",
        "firmware_constraint": ">=5.0",
        "command_vars": {"flow_priority": "high"},
        "raw_template": make_raw_template(),
        "active": True,
    }
    r = real_client.post(f"{API}/provisioning-templates", headers=headers, json=payload)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "pytest-tpl-default"
    assert body["version"] == "1"
    assert body["template_scope"] == "onu_provision"
    assert body["created_by_user_id"] is not None
    assert body["raw_template"]["steps"][0]["step_key"] == "authorize_onu"


def test_create_template_without_olt_model_success(real_client):
    headers, _ = _bootstrap_admin(real_client)
    cat = setup_provisioning_catalog(real_client, headers)

    payload = {
        "manufacturer_id": str(cat["manufacturer_id"]),
        "olt_model_id": None,
        "name": "pytest-tpl-generic",
        "raw_template": make_raw_template(),
    }
    r = real_client.post(f"{API}/provisioning-templates", headers=headers, json=payload)
    assert r.status_code == 201, r.text
    assert r.json()["olt_model_id"] is None


# Validações cruzadas
def test_create_template_with_unknown_manufacturer_returns_400(real_client):
    headers, _ = _bootstrap_admin(real_client)
    payload = {
        "manufacturer_id": str(uuid4()),
        "name": "pytest-tpl-x",
        "raw_template": make_raw_template(),
    }
    r = real_client.post(f"{API}/provisioning-templates", headers=headers, json=payload)
    assert r.status_code == 400, r.text


def test_create_template_with_mismatched_olt_model_returns_400(real_client):
    headers, _ = _bootstrap_admin(real_client)
    cat_a = setup_provisioning_catalog(real_client, headers)
    cat_b = setup_provisioning_catalog(real_client, headers)
    # olt_model_id de B com manufacturer de A: mismatch
    payload = {
        "manufacturer_id": str(cat_a["manufacturer_id"]),
        "olt_model_id": str(cat_b["olt_model_id"]),
        "name": "pytest-tpl-mismatch",
        "raw_template": make_raw_template(),
    }
    r = real_client.post(f"{API}/provisioning-templates", headers=headers, json=payload)
    assert r.status_code == 400, r.text


def test_create_template_with_scope_mismatch_returns_422(real_client):
    headers, _ = _bootstrap_admin(real_client)
    cat = setup_provisioning_catalog(real_client, headers)
    payload = {
        "manufacturer_id": str(cat["manufacturer_id"]),
        "template_scope": "onu_provision",
        "name": "pytest-tpl-scope",
        # raw_template.scope diverge de template_scope
        "raw_template": make_raw_template(scope="vlan_config"),
    }
    r = real_client.post(f"{API}/provisioning-templates", headers=headers, json=payload)
    assert r.status_code == 422, r.text


# Unicidade


def test_create_template_duplicate_key_returns_409(real_client):
    headers, _ = _bootstrap_admin(real_client)
    cat = setup_provisioning_catalog(real_client, headers)
    payload = {
        "manufacturer_id": str(cat["manufacturer_id"]),
        "olt_model_id": str(cat["olt_model_id"]),
        "name": "pytest-tpl-dup",
        "version": "1",
        "raw_template": make_raw_template(),
    }
    r1 = real_client.post(f"{API}/provisioning-templates", headers=headers, json=payload)
    assert r1.status_code == 201, r1.text
    r2 = real_client.post(f"{API}/provisioning-templates", headers=headers, json=payload)
    assert r2.status_code == 409, r2.text


def test_create_template_same_name_different_version_allowed(real_client):
    headers, _ = _bootstrap_admin(real_client)
    cat = setup_provisioning_catalog(real_client, headers)
    base = {
        "manufacturer_id": str(cat["manufacturer_id"]),
        "olt_model_id": str(cat["olt_model_id"]),
        "name": "pytest-tpl-versioned",
        "raw_template": make_raw_template(),
    }
    r1 = real_client.post(
        f"{API}/provisioning-templates", headers=headers, json={**base, "version": "1"}
    )
    assert r1.status_code == 201, r1.text
    r2 = real_client.post(
        f"{API}/provisioning-templates", headers=headers, json={**base, "version": "2"}
    )
    assert r2.status_code == 201, r2.text


# GET / list


def test_get_template_returns_full_payload(real_client):
    headers, _ = _bootstrap_admin(real_client)
    cat = setup_provisioning_catalog(real_client, headers)
    r = real_client.post(
        f"{API}/provisioning-templates",
        headers=headers,
        json={
            "manufacturer_id": str(cat["manufacturer_id"]),
            "name": "pytest-tpl-get",
            "raw_template": make_raw_template(),
        },
    )
    template_id = r.json()["provisioning_template_id"]
    r = real_client.get(f"{API}/provisioning-templates/{template_id}", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["provisioning_template_id"] == template_id


def test_list_templates_with_filter_by_manufacturer(real_client):
    headers, _ = _bootstrap_admin(real_client)
    cat = setup_provisioning_catalog(real_client, headers)
    for v in ("1", "2", "3"):
        real_client.post(
            f"{API}/provisioning-templates",
            headers=headers,
            json={
                "manufacturer_id": str(cat["manufacturer_id"]),
                "name": "pytest-tpl-list",
                "version": v,
                "raw_template": make_raw_template(),
            },
        )
    r = real_client.get(
        f"{API}/provisioning-templates",
        headers=headers,
        params={"manufacturer_id": str(cat["manufacturer_id"])},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] >= 3
    assert all(item["manufacturer_id"] == str(cat["manufacturer_id"]) for item in body["items"])


# PATCH


def test_patch_template_active_flag(real_client):
    headers, _ = _bootstrap_admin(real_client)
    cat = setup_provisioning_catalog(real_client, headers)
    r = real_client.post(
        f"{API}/provisioning-templates",
        headers=headers,
        json={
            "manufacturer_id": str(cat["manufacturer_id"]),
            "name": "pytest-tpl-patch",
            "raw_template": make_raw_template(),
        },
    )
    template_id = r.json()["provisioning_template_id"]
    r = real_client.patch(
        f"{API}/provisioning-templates/{template_id}",
        headers=headers,
        json={"active": False},
    )
    assert r.status_code == 200, r.text
    assert r.json()["active"] is False


def test_patch_template_scope_in_raw_template_must_match_column(real_client):
    headers, _ = _bootstrap_admin(real_client)
    cat = setup_provisioning_catalog(real_client, headers)
    r = real_client.post(
        f"{API}/provisioning-templates",
        headers=headers,
        json={
            "manufacturer_id": str(cat["manufacturer_id"]),
            "template_scope": "onu_provision",
            "name": "pytest-tpl-patch-scope",
            "raw_template": make_raw_template(),
        },
    )
    template_id = r.json()["provisioning_template_id"]
    r = real_client.patch(
        f"{API}/provisioning-templates/{template_id}",
        headers=headers,
        json={"raw_template": make_raw_template(scope="vlan_config")},
    )
    assert r.status_code == 422, r.text


# Auth


def test_routes_require_admin(real_client):
    # sem header Authorization -> 401
    r = real_client.get(f"{API}/provisioning-templates")
    assert r.status_code == 401, r.text
