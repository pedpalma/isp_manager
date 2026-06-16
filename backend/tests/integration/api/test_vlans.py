from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from tests.integration.api.test_chassis import _create_olt


@pytest.fixture()
def olt_fx(real_client: Any) -> dict[str, Any]:
    return _create_olt(real_client)


class TestVlanCRUD:
    def test_create_vlan(self, real_client: Any, olt_fx: dict[str, Any]) -> None:
        resp = real_client.post(
            "/api/v1/vlans",
            json={
                "olt_id": olt_fx["olt_id"],
                "vlan_number": 100,
                "name": "dados",
                "type": "data",
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["vlan_number"] == 100
        assert body["olt_id"] == olt_fx["olt_id"]
        assert body["type"] == "data"
        assert body["active"] is True

    def test_get_vlan(self, real_client: Any, olt_fx: dict[str, Any]) -> None:
        created = real_client.post(
            "/api/v1/vlans",
            json={"olt_id": olt_fx["olt_id"], "vlan_number": 110},
        ).json()
        resp = real_client.get(f"/api/v1/vlans/{created['vlan_id']}")
        assert resp.status_code == 200
        assert resp.json()["vlan_id"] == created["vlan_id"]

    def test_get_nonexistent_returns_404(self, real_client: Any) -> None:
        assert real_client.get(f"/api/v1/vlans/{uuid4()}").status_code == 404

    def test_list_by_olt(self, real_client: Any, olt_fx: dict[str, Any]) -> None:
        for n in [100, 200, 300]:
            real_client.post(
                "/api/v1/vlans",
                json={"olt_id": olt_fx["olt_id"], "vlan_number": n},
            )
        resp = real_client.get(f"/api/v1/vlans?olt_id={olt_fx['olt_id']}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 3
        numbers = [v["vlan_number"] for v in body["items"]]
        assert numbers == sorted(numbers)

    def test_duplicate_number_returns_409(self, real_client: Any, olt_fx: dict[str, Any]) -> None:
        payload = {"olt_id": olt_fx["olt_id"], "vlan_number": 100}
        assert real_client.post("/api/v1/vlans", json=payload).status_code == 201
        second = real_client.post("/api/v1/vlans", json=payload)
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "conflict"

    def test_invalid_olt_returns_400(self, real_client: Any) -> None:
        resp = real_client.post(
            "/api/v1/vlans",
            json={"olt_id": str(uuid4()), "vlan_number": 100},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "bad_request"

    def test_out_of_range_returns_422(self, real_client: Any, olt_fx: dict[str, Any]) -> None:
        resp = real_client.post(
            "/api/v1/vlans",
            json={"olt_id": olt_fx["olt_id"], "vlan_number": 5000},
        )
        assert resp.status_code == 422

    def test_update_mutable_fields(self, real_client: Any, olt_fx: dict[str, Any]) -> None:
        created = real_client.post(
            "/api/v1/vlans",
            json={"olt_id": olt_fx["olt_id"], "vlan_number": 400, "name": "old"},
        ).json()
        resp = real_client.patch(
            f"/api/v1/vlans/{created['vlan_id']}",
            json={"name": "new", "active": False},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "new"
        assert body["active"] is False

    def test_deactivate_does_not_free_number(
        self, real_client: Any, olt_fx: dict[str, Any]
    ) -> None:
        # D13.3: desativar NAO libera o numero. Recriar a mesma VLAN da 409.
        created = real_client.post(
            "/api/v1/vlans",
            json={"olt_id": olt_fx["olt_id"], "vlan_number": 500},
        ).json()
        real_client.patch(f"/api/v1/vlans/{created['vlan_id']}", json={"active": False})
        dup = real_client.post(
            "/api/v1/vlans",
            json={"olt_id": olt_fx["olt_id"], "vlan_number": 500},
        )
        assert dup.status_code == 409
