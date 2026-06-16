from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from tests.integration.api.test_chassis import _create_olt


@pytest.fixture()
def olt_fx(real_client: Any) -> dict[str, Any]:
    return _create_olt(real_client)


class TestServiceProfileCRUD:
    def test_create(self, real_client: Any, olt_fx: dict[str, Any]) -> None:
        resp = real_client.post(
            "/api/v1/service-profiles",
            json={
                "olt_id": olt_fx["olt_id"],
                "name": "SVC_INTERNET",
                "raw_config": {"vlan": 100},
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["name"] == "SVC_INTERNET"
        assert body["version"] == "1"
        assert body["raw_config"]["vlan"] == 100

    def test_get(self, real_client: Any, olt_fx: dict[str, Any]) -> None:
        created = real_client.post(
            "/api/v1/service-profiles",
            json={"olt_id": olt_fx["olt_id"], "name": "SP1"},
        ).json()
        resp = real_client.get(f"/api/v1/service-profiles/{created['service_profile_id']}")
        assert resp.status_code == 200
        assert resp.json()["service_profile_id"] == created["service_profile_id"]

    def test_get_nonexistent_404(self, real_client: Any) -> None:
        assert real_client.get(f"/api/v1/service-profiles/{uuid4()}").status_code == 404

    def test_list_by_olt(self, real_client: Any, olt_fx: dict[str, Any]) -> None:
        for nm in ["A", "B"]:
            real_client.post(
                "/api/v1/service-profiles",
                json={"olt_id": olt_fx["olt_id"], "name": nm},
            )
        resp = real_client.get(f"/api/v1/service-profiles?olt_id={olt_fx['olt_id']}")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 2

    def test_duplicate_name_version_409(self, real_client: Any, olt_fx: dict[str, Any]) -> None:
        payload = {"olt_id": olt_fx["olt_id"], "name": "DUP", "version": "1"}
        assert real_client.post("/api/v1/service-profiles", json=payload).status_code == 201
        second = real_client.post("/api/v1/service-profiles", json=payload)
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "conflict"

    def test_invalid_olt_400(self, real_client: Any) -> None:
        resp = real_client.post(
            "/api/v1/service-profiles",
            json={"olt_id": str(uuid4()), "name": "X"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "bad_request"

    def test_update_logical_name_and_raw_config(
        self, real_client: Any, olt_fx: dict[str, Any]
    ) -> None:
        created = real_client.post(
            "/api/v1/service-profiles",
            json={"olt_id": olt_fx["olt_id"], "name": "UP"},
        ).json()
        resp = real_client.patch(
            f"/api/v1/service-profiles/{created['service_profile_id']}",
            json={"logical_name": "GLOBAL", "raw_config": {"x": 1}},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["logical_name"] == "GLOBAL"
        assert body["raw_config"]["x"] == 1
