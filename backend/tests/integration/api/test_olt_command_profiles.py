# Testes de integração de /api/v1/olt-command-profiles.

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.integration.api.test_auth import _bootstrap_admin, _login  # noqa: F401
from tests.integration.api.test_chassis import (
    _create_manufacturer,
    _create_olt_model,
)


def _unique(prefix: str) -> str:
    return f"pytest-{prefix}-{uuid4().hex[:8]}"


@pytest.fixture
def admin_headers(real_client: TestClient) -> dict[str, str]:
    headers, _username = _bootstrap_admin(real_client)
    return headers


@pytest.fixture
def olt_model_id(real_client: TestClient, admin_headers: dict[str, str]) -> str:
    del admin_headers
    mfr = _create_manufacturer(real_client)
    olt_model = _create_olt_model(real_client, mfr["manufacturer_id"])
    return olt_model["olt_model_id"]


# CREATE


def test_create_returns_201_and_echoes(
    real_client: TestClient,
    admin_headers: dict[str, str],
    olt_model_id: str,
) -> None:
    payload = {
        "olt_model_id": olt_model_id,
        "firmware_version": "6.0.0",
        "access_protocol": "SSH",
        "version_constraint": ">=6.0,<7.0",
        "parser_profile": "fh-v6-default",
    }
    resp = real_client.post(
        "/api/v1/olt-command-profiles",
        json=payload,
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["olt_model_id"] == olt_model_id
    assert body["firmware_version"] == "6.0.0"
    assert body["access_protocol"] == "SSH"
    assert body["version_constraint"] == ">=6.0,<7.0"
    assert body["parser_profile"] == "fh-v6-default"
    assert body["active"] is True
    assert "olt_command_profile_id" in body
    assert "created_at" in body
    assert "updated_at" in body


def test_create_defaults_ssh_when_protocol_omitted(
    real_client: TestClient,
    admin_headers: dict[str, str],
    olt_model_id: str,
) -> None:
    payload = {
        "olt_model_id": olt_model_id,
        "firmware_version": "7.0.0",
    }
    resp = real_client.post(
        "/api/v1/olt-command-profiles",
        json=payload,
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["access_protocol"] == "SSH"


def test_create_strips_firmware_version(
    real_client: TestClient,
    admin_headers: dict[str, str],
    olt_model_id: str,
) -> None:
    payload = {
        "olt_model_id": olt_model_id,
        "firmware_version": "  6.1.0  ",
    }
    resp = real_client.post(
        "/api/v1/olt-command-profiles",
        json=payload,
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["firmware_version"] == "6.1.0"


# CONFLITO (unicidade TOTAL)


def test_duplicate_returns_409(
    real_client: TestClient,
    admin_headers: dict[str, str],
    olt_model_id: str,
) -> None:
    payload = {
        "olt_model_id": olt_model_id,
        "firmware_version": "6.2.0",
        "access_protocol": "SSH",
    }
    resp1 = real_client.post("/api/v1/olt-command-profiles", json=payload, headers=admin_headers)
    assert resp1.status_code == 201, resp1.text

    resp2 = real_client.post("/api/v1/olt-command-profiles", json=payload, headers=admin_headers)
    assert resp2.status_code == 409, resp2.text
    body = resp2.json()
    assert body["error"]["code"] == "conflict"
    assert body["error"]["details"]["firmware_version"] == "6.2.0"


def test_same_firmware_different_protocol_is_allowed(
    real_client: TestClient,
    admin_headers: dict[str, str],
    olt_model_id: str,
) -> None:
    """Unicidade TOTAL é sobre (olt_model_id, firmware, protocol);
    trocar o protocolo abre nova chave."""
    base = {
        "olt_model_id": olt_model_id,
        "firmware_version": "6.3.0",
    }
    r1 = real_client.post(
        "/api/v1/olt-command-profiles",
        json={**base, "access_protocol": "SSH"},
        headers=admin_headers,
    )
    r2 = real_client.post(
        "/api/v1/olt-command-profiles",
        json={**base, "access_protocol": "TELNET"},
        headers=admin_headers,
    )
    assert r1.status_code == 201, r1.text
    assert r2.status_code == 201, r2.text


# FK INVÁLIDA


def test_invalid_olt_model_returns_400(
    real_client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    payload = {
        "olt_model_id": str(uuid4()),
        "firmware_version": "6.0.0",
    }
    resp = real_client.post("/api/v1/olt-command-profiles", json=payload, headers=admin_headers)
    assert resp.status_code == 400, resp.text
    assert resp.json()["error"]["code"] == "bad_request"


# GET


def test_get_returns_created_profile(
    real_client: TestClient,
    admin_headers: dict[str, str],
    olt_model_id: str,
) -> None:
    created = real_client.post(
        "/api/v1/olt-command-profiles",
        json={"olt_model_id": olt_model_id, "firmware_version": "6.4.0"},
        headers=admin_headers,
    ).json()
    profile_id = created["olt_command_profile_id"]

    resp = real_client.get(f"/api/v1/olt-command-profiles/{profile_id}", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["olt_command_profile_id"] == profile_id


def test_get_nonexistent_returns_404(
    real_client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    resp = real_client.get(f"/api/v1/olt-command-profiles/{uuid4()}", headers=admin_headers)
    assert resp.status_code == 404, resp.text
    assert resp.json()["error"]["code"] == "not_found"


# LIST


def test_list_paginated_filter_by_olt_model(
    real_client: TestClient,
    admin_headers: dict[str, str],
    olt_model_id: str,
) -> None:
    for fw in ("6.5.0", "6.6.0", "6.7.0"):
        real_client.post(
            "/api/v1/olt-command-profiles",
            json={"olt_model_id": olt_model_id, "firmware_version": fw},
            headers=admin_headers,
        )
    resp = real_client.get(
        "/api/v1/olt-command-profiles",
        params={"olt_model_id": olt_model_id, "page": 1, "page_size": 50},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] >= 3
    assert body["page"] == 1
    assert body["page_size"] == 50
    fws = {i["firmware_version"] for i in body["items"]}
    assert {"6.5.0", "6.6.0", "6.7.0"}.issubset(fws)


# PATCH


def test_update_mutable_fields(
    real_client: TestClient,
    admin_headers: dict[str, str],
    olt_model_id: str,
) -> None:
    created = real_client.post(
        "/api/v1/olt-command-profiles",
        json={"olt_model_id": olt_model_id, "firmware_version": "6.8.0"},
        headers=admin_headers,
    ).json()
    profile_id = created["olt_command_profile_id"]

    resp = real_client.patch(
        f"/api/v1/olt-command-profiles/{profile_id}",
        json={
            "version_constraint": ">=6.8,<7.0",
            "parser_profile": "fh-v6-tuned",
            "active": False,
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["version_constraint"] == ">=6.8,<7.0"
    assert body["parser_profile"] == "fh-v6-tuned"
    assert body["active"] is False


def test_update_empty_payload_is_noop(
    real_client: TestClient,
    admin_headers: dict[str, str],
    olt_model_id: str,
) -> None:
    created = real_client.post(
        "/api/v1/olt-command-profiles",
        json={"olt_model_id": olt_model_id, "firmware_version": "6.9.0"},
        headers=admin_headers,
    ).json()
    profile_id = created["olt_command_profile_id"]

    resp = real_client.patch(
        f"/api/v1/olt-command-profiles/{profile_id}",
        json={},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["olt_command_profile_id"] == profile_id


# AUTH


def test_requires_authentication(real_client: TestClient) -> None:
    resp = real_client.get("/api/v1/olt-command-profiles")
    assert resp.status_code == 401, resp.text


# 422 (payload malformado)


def test_missing_firmware_returns_422(
    real_client: TestClient,
    admin_headers: dict[str, str],
    olt_model_id: str,
) -> None:
    resp = real_client.post(
        "/api/v1/olt-command-profiles",
        json={"olt_model_id": olt_model_id},
        headers=admin_headers,
    )
    assert resp.status_code == 422, resp.text


def test_extra_field_rejected_422(
    real_client: TestClient,
    admin_headers: dict[str, str],
    olt_model_id: str,
) -> None:
    resp = real_client.post(
        "/api/v1/olt-command-profiles",
        json={
            "olt_model_id": olt_model_id,
            "firmware_version": "7.1.0",
            "unexpected_field": "should_fail",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 422, resp.text
