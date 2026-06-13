from __future__ import annotations

import secrets
from typing import Any
from uuid import uuid4

import pytest


def _suffix() -> str:
    return secrets.token_hex(4)


@pytest.fixture()
def chassis_fx(real_client: Any) -> dict[str, Any]:
    # Reaproveita o helper do teste de chassis (importado dinamicamente).
    from tests.integration.api.test_chassis import _create_olt  # noqa: PLC0415

    olt = _create_olt(real_client)
    resp = real_client.post(
        "/api/v1/chassis",
        json={"olt_id": olt["olt_id"], "chassis_index": 0},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestSlotCRUD:
    def test_create_slot(self, real_client: Any, chassis_fx: dict[str, Any]) -> None:
        resp = real_client.post(
            "/api/v1/slots",
            json={"chassis_id": chassis_fx["chassis_id"], "slot_index": 1, "board_type": "GTGH"},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        # status default 'unknown' vem via RETURNING do banco.
        assert body["status"] == "unknown"
        assert body["board_type"] == "GTGH"

    def test_duplicate_returns_409(self, real_client: Any, chassis_fx: dict[str, Any]) -> None:
        payload = {"chassis_id": chassis_fx["chassis_id"], "slot_index": 2}
        first = real_client.post("/api/v1/slots", json=payload)
        assert first.status_code == 201
        second = real_client.post("/api/v1/slots", json=payload)
        assert second.status_code == 409

    def test_invalid_chassis_returns_400(self, real_client: Any) -> None:
        resp = real_client.post(
            "/api/v1/slots",
            json={"chassis_id": str(uuid4()), "slot_index": 0},
        )
        assert resp.status_code == 400

    def test_list_by_chassis(self, real_client: Any, chassis_fx: dict[str, Any]) -> None:
        for idx in [10, 11, 12]:
            real_client.post(
                "/api/v1/slots",
                json={"chassis_id": chassis_fx["chassis_id"], "slot_index": idx},
            )
        resp = real_client.get(f"/api/v1/slots?chassis_id={chassis_fx['chassis_id']}")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 3

    def test_update_status_to_disabled(self, real_client: Any, chassis_fx: dict[str, Any]) -> None:
        created = real_client.post(
            "/api/v1/slots",
            json={"chassis_id": chassis_fx["chassis_id"], "slot_index": 20},
        ).json()
        resp = real_client.patch(
            f"/api/v1/slots/{created['slot_id']}",
            json={"status": "disabled"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "disabled"

    def test_update_status_to_up_returns_400(
        self, real_client: Any, chassis_fx: dict[str, Any]
    ) -> None:
        """up' é exclusivo da Coleta. App não pode setar."""
        created = real_client.post(
            "/api/v1/slots",
            json={"chassis_id": chassis_fx["chassis_id"], "slot_index": 21},
        ).json()
        resp = real_client.patch(
            f"/api/v1/slots/{created['slot_id']}",
            json={"status": "up"},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "bad_request"

    def test_update_board_type(self, real_client: Any, chassis_fx: dict[str, Any]) -> None:
        created = real_client.post(
            "/api/v1/slots",
            json={"chassis_id": chassis_fx["chassis_id"], "slot_index": 22, "board_type": "old"},
        ).json()
        resp = real_client.patch(
            f"/api/v1/slots/{created['slot_id']}",
            json={"board_type": "new"},
        )
        assert resp.status_code == 200
        assert resp.json()["board_type"] == "new"
