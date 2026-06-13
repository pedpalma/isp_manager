from __future__ import annotations

import secrets
from typing import Any
from uuid import uuid4

import pytest


def _suffix() -> str:
    return secrets.token_hex(4)


@pytest.fixture()
def slot_fx(real_client: Any) -> dict[str, Any]:
    from tests.integration.api.test_chassis import _create_olt  # noqa: PLC0415

    olt = _create_olt(real_client)
    chassis = real_client.post(
        "/api/v1/chassis",
        json={"olt_id": olt["olt_id"], "chassis_index": 0},
    ).json()
    slot = real_client.post(
        "/api/v1/slots",
        json={"chassis_id": chassis["chassis_id"], "slot_index": 1},
    ).json()
    return slot


class TestPonPortCRUD:
    def test_create_with_default_gpon(self, real_client: Any, slot_fx: dict[str, Any]) -> None:
        resp = real_client.post(
            "/api/v1/pon-ports",
            json={"slot_id": slot_fx["slot_id"], "pon_index": 1},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["pon_type"] == "GPON"
        assert body["status"] == "unknown"

    def test_create_with_xg_pon(self, real_client: Any, slot_fx: dict[str, Any]) -> None:
        """Confirma que a migration 0002 (XGSPON -> XG-PON) está aplicada."""
        resp = real_client.post(
            "/api/v1/pon-ports",
            json={"slot_id": slot_fx["slot_id"], "pon_index": 2, "pon_type": "XG-PON"},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["pon_type"] == "XG-PON"

    def test_duplicate_returns_409(self, real_client: Any, slot_fx: dict[str, Any]) -> None:
        payload = {"slot_id": slot_fx["slot_id"], "pon_index": 3}
        first = real_client.post("/api/v1/pon-ports", json=payload)
        assert first.status_code == 201
        second = real_client.post("/api/v1/pon-ports", json=payload)
        assert second.status_code == 409

    def test_invalid_slot_returns_400(self, real_client: Any) -> None:
        resp = real_client.post(
            "/api/v1/pon-ports",
            json={"slot_id": str(uuid4()), "pon_index": 0},
        )
        assert resp.status_code == 400

    def test_list_by_slot(self, real_client: Any, slot_fx: dict[str, Any]) -> None:
        for idx in [10, 11, 12]:
            real_client.post(
                "/api/v1/pon-ports",
                json={"slot_id": slot_fx["slot_id"], "pon_index": idx},
            )
        resp = real_client.get(f"/api/v1/pon-ports?slot_id={slot_fx['slot_id']}")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 3

    def test_update_status_to_disabled(self, real_client: Any, slot_fx: dict[str, Any]) -> None:
        created = real_client.post(
            "/api/v1/pon-ports",
            json={"slot_id": slot_fx["slot_id"], "pon_index": 20},
        ).json()
        resp = real_client.patch(
            f"/api/v1/pon-ports/{created['pon_port_id']}",
            json={"status": "disabled"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "disabled"

    def test_update_status_to_faulty_returns_400(
        self, real_client: Any, slot_fx: dict[str, Any]
    ) -> None:
        created = real_client.post(
            "/api/v1/pon-ports",
            json={"slot_id": slot_fx["slot_id"], "pon_index": 21},
        ).json()
        resp = real_client.patch(
            f"/api/v1/pon-ports/{created['pon_port_id']}",
            json={"status": "faulty"},
        )
        assert resp.status_code == 400
