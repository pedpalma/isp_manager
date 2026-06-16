from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from tests.integration.api.test_chassis import _create_olt


@pytest.fixture()
def olt_fx(real_client: Any) -> dict[str, Any]:
    return _create_olt(real_client)


def _base(olt_id: str, **over: Any) -> dict[str, Any]:
    body = {
        "olt_id": olt_id,
        "name": "P",
        "upstream_bandwidth": "1G",
        "downstream_bandwidth": "1G",
    }
    body.update(over)
    return body


class TestLineProfileCRUD:
    def test_create(self, real_client: Any, olt_fx: dict[str, Any]) -> None:
        resp = real_client.post(
            "/api/v1/line-profiles",
            json=_base(
                olt_fx["olt_id"],
                name="PLANO_600M",
                upstream_bandwidth="600M",
                downstream_bandwidth="600M",
            ),
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["name"] == "PLANO_600M"
        assert body["version"] == "1"
        assert body["active"] is True

    def test_get(self, real_client: Any, olt_fx: dict[str, Any]) -> None:
        created = real_client.post(
            "/api/v1/line-profiles", json=_base(olt_fx["olt_id"], name="LP1")
        ).json()
        resp = real_client.get(f"/api/v1/line-profiles/{created['line_profile_id']}")
        assert resp.status_code == 200
        assert resp.json()["line_profile_id"] == created["line_profile_id"]

    def test_get_nonexistent_404(self, real_client: Any) -> None:
        assert real_client.get(f"/api/v1/line-profiles/{uuid4()}").status_code == 404

    def test_list_by_olt(self, real_client: Any, olt_fx: dict[str, Any]) -> None:
        for nm in ["A", "B", "C"]:
            real_client.post("/api/v1/line-profiles", json=_base(olt_fx["olt_id"], name=nm))
        resp = real_client.get(f"/api/v1/line-profiles?olt_id={olt_fx['olt_id']}")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 3

    def test_same_name_different_version_ok(self, real_client: Any, olt_fx: dict[str, Any]) -> None:
        first = real_client.post(
            "/api/v1/line-profiles",
            json=_base(olt_fx["olt_id"], name="PLANO", version="1"),
        )
        assert first.status_code == 201
        second = real_client.post(
            "/api/v1/line-profiles",
            json=_base(olt_fx["olt_id"], name="PLANO", version="2"),
        )
        assert second.status_code == 201

    def test_duplicate_name_version_409(self, real_client: Any, olt_fx: dict[str, Any]) -> None:
        payload = _base(olt_fx["olt_id"], name="DUP", version="1")
        assert real_client.post("/api/v1/line-profiles", json=payload).status_code == 201
        second = real_client.post("/api/v1/line-profiles", json=payload)
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "conflict"

    def test_invalid_olt_400(self, real_client: Any) -> None:
        resp = real_client.post("/api/v1/line-profiles", json=_base(str(uuid4()), name="X"))
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "bad_request"

    def test_update_bandwidth_and_logical_name(
        self, real_client: Any, olt_fx: dict[str, Any]
    ) -> None:
        created = real_client.post(
            "/api/v1/line-profiles", json=_base(olt_fx["olt_id"], name="UP")
        ).json()
        resp = real_client.patch(
            f"/api/v1/line-profiles/{created['line_profile_id']}",
            json={"upstream_bandwidth": "2G", "logical_name": "PLANO_2G"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["upstream_bandwidth"] == "2G"
        assert body["logical_name"] == "PLANO_2G"
