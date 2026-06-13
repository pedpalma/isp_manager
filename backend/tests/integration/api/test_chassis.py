from __future__ import annotations

import secrets
from typing import Any
from uuid import uuid4

import pytest


def _suffix() -> str:
    return secrets.token_hex(4)


def _create_manufacturer(real_client: Any) -> dict[str, Any]:
    s = _suffix()
    resp = real_client.post(
        "/api/v1/manufacturers",
        json={"name": f"pytest-Mfr-{s}", "slug": f"pytest-mfr-{s}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_olt_model(real_client: Any, manufacturer_id: str) -> dict[str, Any]:
    s = _suffix()
    resp = real_client.post(
        "/api/v1/olt-models",
        json={"manufacturer_id": manufacturer_id, "model": f"pytest-Model-{s}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_credential(real_client: Any) -> dict[str, Any]:
    s = _suffix()
    resp = real_client.post(
        "/api/v1/credentials",
        json={
            "label": f"pytest-Cred-{s}",
            "username": f"adm-{s}",
            "secret_ref": f"env:PYTEST_SECRET_{s.upper()}",
            "auth_type": "password",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_olt(real_client: Any) -> dict[str, Any]:
    mfr = _create_manufacturer(real_client)
    olt_model = _create_olt_model(real_client, mfr["manufacturer_id"])
    cred = _create_credential(real_client)
    s = _suffix()
    resp = real_client.post(
        "/api/v1/olts",
        json={
            "name": f"pytest-olt-{s}",
            "ip": f"10.99.{secrets.randbelow(255)}.{secrets.randbelow(255)}",
            "management_port": 22,
            "olt_model_id": olt_model["olt_model_id"],
            "credential_id": cred["credential_id"],
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture()
def olt_fx(real_client: Any) -> dict[str, Any]:
    return _create_olt(real_client)


class TestChassisCRUD:
    def test_create_chassis(self, real_client: Any, olt_fx: dict[str, Any]) -> None:
        resp = real_client.post(
            "/api/v1/chassis",
            json={
                "olt_id": olt_fx["olt_id"],
                "chassis_index": 0,
                "description": "primeiro chassis",
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["chassis_index"] == 0
        assert body["olt_id"] == olt_fx["olt_id"]
        assert body["description"] == "primeiro chassis"
        assert body["discovered_at"] is None  # Coleta preencherá

    def test_get_chassis(self, real_client: Any, olt_fx: dict[str, Any]) -> None:
        created = real_client.post(
            "/api/v1/chassis",
            json={"olt_id": olt_fx["olt_id"], "chassis_index": 1},
        ).json()
        resp = real_client.get(f"/api/v1/chassis/{created['chassis_id']}")
        assert resp.status_code == 200
        assert resp.json()["chassis_id"] == created["chassis_id"]

    def test_get_nonexistent_returns_404(self, real_client: Any) -> None:
        resp = real_client.get(f"/api/v1/chassis/{uuid4()}")
        assert resp.status_code == 404

    def test_list_by_olt(self, real_client: Any, olt_fx: dict[str, Any]) -> None:
        for idx in [0, 1, 2]:
            real_client.post(
                "/api/v1/chassis",
                json={"olt_id": olt_fx["olt_id"], "chassis_index": idx},
            )
        resp = real_client.get(f"/api/v1/chassis?olt_id={olt_fx['olt_id']}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 3
        indexes = [c["chassis_index"] for c in body["items"]]
        assert indexes == sorted(indexes)  # ordenado

    def test_duplicate_index_returns_409(self, real_client: Any, olt_fx: dict[str, Any]) -> None:
        payload = {"olt_id": olt_fx["olt_id"], "chassis_index": 0}
        first = real_client.post("/api/v1/chassis", json=payload)
        assert first.status_code == 201
        second = real_client.post("/api/v1/chassis", json=payload)
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "conflict"

    def test_invalid_olt_returns_400(self, real_client: Any) -> None:
        resp = real_client.post(
            "/api/v1/chassis",
            json={"olt_id": str(uuid4()), "chassis_index": 0},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "bad_request"

    def test_update_description(self, real_client: Any, olt_fx: dict[str, Any]) -> None:
        created = real_client.post(
            "/api/v1/chassis",
            json={"olt_id": olt_fx["olt_id"], "chassis_index": 5, "description": "old"},
        ).json()
        resp = real_client.patch(
            f"/api/v1/chassis/{created['chassis_id']}",
            json={"description": "new"},
        )
        assert resp.status_code == 200
        assert resp.json()["description"] == "new"

    def test_update_cannot_change_index(self, real_client: Any, olt_fx: dict[str, Any]) -> None:
        created = real_client.post(
            "/api/v1/chassis",
            json={"olt_id": olt_fx["olt_id"], "chassis_index": 7},
        ).json()
        # chassis_index não está no schema de Update; Pydantic ignora silenciosamente
        # (extra='ignore' é o default), então a operação retorna 200 sem efeito.
        resp = real_client.patch(
            f"/api/v1/chassis/{created['chassis_id']}",
            json={"chassis_index": 999},
        )
        assert resp.status_code == 200
        assert resp.json()["chassis_index"] == 7
