from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest


@pytest.fixture()
def olt_with_topology(real_client: Any) -> dict[str, Any]:
    from tests.integration.api.test_chassis import _create_olt  # noqa: PLC0415

    olt = _create_olt(real_client)
    # 2 chassis, cada um com 2 slots, cada slot com 2 pon_ports.
    for ci in [0, 1]:
        chassis = real_client.post(
            "/api/v1/chassis",
            json={"olt_id": olt["olt_id"], "chassis_index": ci},
        ).json()
        for si in [0, 1]:
            slot = real_client.post(
                "/api/v1/slots",
                json={"chassis_id": chassis["chassis_id"], "slot_index": si},
            ).json()
            for pi in [0, 1]:
                real_client.post(
                    "/api/v1/pon-ports",
                    json={"slot_id": slot["slot_id"], "pon_index": pi},
                )
    return olt


class TestTopology:
    def test_topology_returns_full_tree(
        self, real_client: Any, olt_with_topology: dict[str, Any]
    ) -> None:
        resp = real_client.get(f"/api/v1/olts/{olt_with_topology['olt_id']}/topology")
        assert resp.status_code == 200
        body = resp.json()
        assert body["olt_id"] == olt_with_topology["olt_id"]
        assert body["name"] == olt_with_topology["name"]
        assert len(body["chassis"]) == 2
        for c in body["chassis"]:
            assert len(c["slots"]) == 2
            for s in c["slots"]:
                assert len(s["pon_ports"]) == 2

    def test_topology_for_empty_olt(self, real_client: Any) -> None:
        from tests.integration.api.test_chassis import _create_olt  # noqa: PLC0415

        olt = _create_olt(real_client)
        resp = real_client.get(f"/api/v1/olts/{olt['olt_id']}/topology")
        assert resp.status_code == 200
        assert resp.json()["chassis"] == []

    def test_topology_for_nonexistent_olt(self, real_client: Any) -> None:
        resp = real_client.get(f"/api/v1/olts/{uuid4()}/topology")
        assert resp.status_code == 404

    def test_topology_for_soft_deleted_olt_returns_404(
        self, real_client: Any, olt_with_topology: dict[str, Any]
    ) -> None:
        """OLT soft-deleted é como se não existisse para o domínio."""
        olt_id = olt_with_topology["olt_id"]
        del_resp = real_client.delete(f"/api/v1/olts/{olt_id}")
        assert del_resp.status_code == 204
        resp = real_client.get(f"/api/v1/olts/{olt_id}/topology")
        assert resp.status_code == 404
