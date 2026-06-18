from __future__ import annotations

import secrets
from typing import Any
from uuid import uuid4

import pytest


def _suffix() -> str:
    return secrets.token_hex(4)


def _create_onu_model(real_client: Any) -> dict[str, Any]:
    s = _suffix()
    mfr = real_client.post(
        "/api/v1/manufacturers",
        json={"name": f"pytest-Mfr-{s}", "slug": f"pytest-mfr-{s}"},
    )
    assert mfr.status_code == 201, mfr.text
    mfr_body = mfr.json()
    resp = real_client.post(
        "/api/v1/onu-models",
        json={
            "manufacturer_id": mfr_body["manufacturer_id"],
            "model": f"pytest-OnuModel-{s}",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _add_pon_port(real_client: Any, slot_id: str, pon_index: int) -> dict[str, Any]:
    resp = real_client.post(
        "/api/v1/pon-ports",
        json={"slot_id": slot_id, "pon_index": pon_index},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_onu(
    real_client: Any,
    pon_port_id: str,
    onu_model_id: str,
    *,
    serial: str | None = None,
    onu_index: int | None = None,
    description: str | None = None,
) -> Any:
    payload: dict[str, Any] = {
        "onu_model_id": onu_model_id,
        "pon_port_id": pon_port_id,
        "serial": serial or f"PYTEST{_suffix().upper()}",
    }
    if onu_index is not None:
        payload["onu_index"] = onu_index
    if description is not None:
        payload["description"] = description
    return real_client.post("/api/v1/onus", json=payload)


@pytest.fixture()
def chain(real_client: Any) -> dict[str, Any]:
    """OLT -> chassis -> slot -> pon_port. Devolve os ids da cadeia para os testes
    que precisam de uma PON viva (e do slot, para criar PONs irmãs)."""
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
    pon = _add_pon_port(real_client, slot["slot_id"], 1)
    return {
        "olt_id": olt["olt_id"],
        "chassis_id": chassis["chassis_id"],
        "slot_id": slot["slot_id"],
        "pon_port_id": pon["pon_port_id"],
    }


@pytest.fixture()
def onu_model(real_client: Any) -> dict[str, Any]:
    return _create_onu_model(real_client)


class TestOnuCreate:
    def test_create_onu(
        self, real_client: Any, chain: dict[str, Any], onu_model: dict[str, Any]
    ) -> None:
        resp = _create_onu(
            real_client,
            chain["pon_port_id"],
            onu_model["onu_model_id"],
            serial="FHTT12345678",
            onu_index=3,
            description="cliente teste",
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["serial"] == "FHTT12345678"
        assert body["pon_port_id"] == chain["pon_port_id"]
        assert body["onu_model_id"] == onu_model["onu_model_id"]
        assert body["onu_index"] == 3
        assert body["description"] == "cliente teste"
        # provisioned tem default no banco (False); a Coleta/provisionamento muda.
        assert body["provisioned"] is False
        # Runtime criado pela trigger e embutido no detalhe da criação.
        assert body["runtime"] is not None
        assert body["runtime"]["connection_status"] == "unknown"
        assert body["runtime"]["sync_status"] == "pending"

    def test_serial_is_trimmed(
        self, real_client: Any, chain: dict[str, Any], onu_model: dict[str, Any]
    ) -> None:
        resp = _create_onu(
            real_client,
            chain["pon_port_id"],
            onu_model["onu_model_id"],
            serial="  ZTEG11112222  ",
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["serial"] == "ZTEG11112222"

    def test_serial_too_short_returns_422(
        self, real_client: Any, chain: dict[str, Any], onu_model: dict[str, Any]
    ) -> None:
        resp = _create_onu(
            real_client, chain["pon_port_id"], onu_model["onu_model_id"], serial="ab"
        )
        assert resp.status_code == 422

    def test_onu_index_out_of_range_returns_422(
        self, real_client: Any, chain: dict[str, Any], onu_model: dict[str, Any]
    ) -> None:
        resp = _create_onu(
            real_client,
            chain["pon_port_id"],
            onu_model["onu_model_id"],
            onu_index=5000,
        )
        assert resp.status_code == 422

    def test_invalid_pon_port_returns_400(
        self, real_client: Any, onu_model: dict[str, Any]
    ) -> None:
        resp = _create_onu(real_client, str(uuid4()), onu_model["onu_model_id"])
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "bad_request"

    def test_invalid_onu_model_returns_400(self, real_client: Any, chain: dict[str, Any]) -> None:
        resp = _create_onu(real_client, chain["pon_port_id"], str(uuid4()))
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "bad_request"

    def test_duplicate_serial_returns_409(
        self, real_client: Any, chain: dict[str, Any], onu_model: dict[str, Any]
    ) -> None:
        first = _create_onu(
            real_client,
            chain["pon_port_id"],
            onu_model["onu_model_id"],
            serial="DUPSERIAL001",
        )
        assert first.status_code == 201
        second = _create_onu(
            real_client,
            chain["pon_port_id"],
            onu_model["onu_model_id"],
            serial="DUPSERIAL001",
        )
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "conflict"

    def test_duplicate_index_per_pon_returns_409(
        self, real_client: Any, chain: dict[str, Any], onu_model: dict[str, Any]
    ) -> None:
        first = _create_onu(
            real_client, chain["pon_port_id"], onu_model["onu_model_id"], onu_index=7
        )
        assert first.status_code == 201
        second = _create_onu(
            real_client, chain["pon_port_id"], onu_model["onu_model_id"], onu_index=7
        )
        assert second.status_code == 409

    def test_same_index_different_pon_is_ok(
        self, real_client: Any, chain: dict[str, Any], onu_model: dict[str, Any]
    ) -> None:
        other_pon = _add_pon_port(real_client, chain["slot_id"], 2)
        a = _create_onu(real_client, chain["pon_port_id"], onu_model["onu_model_id"], onu_index=9)
        b = _create_onu(
            real_client, other_pon["pon_port_id"], onu_model["onu_model_id"], onu_index=9
        )
        assert a.status_code == 201
        assert b.status_code == 201

    def test_null_index_allows_multiple_per_pon(
        self, real_client: Any, chain: dict[str, Any], onu_model: dict[str, Any]
    ) -> None:
        # A unicidade parcial só vale para onu_index NOT NULL.
        a = _create_onu(real_client, chain["pon_port_id"], onu_model["onu_model_id"])
        b = _create_onu(real_client, chain["pon_port_id"], onu_model["onu_model_id"])
        assert a.status_code == 201
        assert b.status_code == 201
        assert a.json()["onu_index"] is None
        assert b.json()["onu_index"] is None


class TestOnuRead:
    def test_get_onu_includes_runtime(
        self, real_client: Any, chain: dict[str, Any], onu_model: dict[str, Any]
    ) -> None:
        created = _create_onu(real_client, chain["pon_port_id"], onu_model["onu_model_id"]).json()
        resp = real_client.get(f"/api/v1/onus/{created['onu_id']}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["onu_id"] == created["onu_id"]
        assert body["runtime"] is not None
        assert body["runtime"]["connection_status"] == "unknown"

    def test_get_nonexistent_returns_404(self, real_client: Any) -> None:
        resp = real_client.get(f"/api/v1/onus/{uuid4()}")
        assert resp.status_code == 404

    def test_list_by_pon(
        self, real_client: Any, chain: dict[str, Any], onu_model: dict[str, Any]
    ) -> None:
        for _ in range(3):
            _create_onu(real_client, chain["pon_port_id"], onu_model["onu_model_id"])
        resp = real_client.get(f"/api/v1/onus?pon_port_id={chain['pon_port_id']}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 3
        # Itens da lista NÃO trazem runtime (forma OnuRead).
        assert all("runtime" not in item for item in body["items"])

    def test_list_by_serial_search(
        self, real_client: Any, chain: dict[str, Any], onu_model: dict[str, Any]
    ) -> None:
        unique = f"FINDME{_suffix().upper()}"
        _create_onu(real_client, chain["pon_port_id"], onu_model["onu_model_id"], serial=unique)
        # Busca parcial, case-insensitive.
        resp = real_client.get(f"/api/v1/onus?serial={unique[:8].lower()}")
        assert resp.status_code == 200
        serials = [item["serial"] for item in resp.json()["items"]]
        assert unique in serials


class TestOnuUpdate:
    def test_update_description(
        self, real_client: Any, chain: dict[str, Any], onu_model: dict[str, Any]
    ) -> None:
        created = _create_onu(
            real_client,
            chain["pon_port_id"],
            onu_model["onu_model_id"],
            description="old",
        ).json()
        resp = real_client.patch(
            f"/api/v1/onus/{created['onu_id']}",
            json={"description": "new"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["description"] == "new"
        assert body["runtime"] is not None  # detalhe continua trazendo runtime

    def test_update_onu_index(
        self, real_client: Any, chain: dict[str, Any], onu_model: dict[str, Any]
    ) -> None:
        created = _create_onu(
            real_client, chain["pon_port_id"], onu_model["onu_model_id"], onu_index=1
        ).json()
        resp = real_client.patch(
            f"/api/v1/onus/{created['onu_id']}",
            json={"onu_index": 2},
        )
        assert resp.status_code == 200
        assert resp.json()["onu_index"] == 2

    def test_update_index_conflict_returns_409(
        self, real_client: Any, chain: dict[str, Any], onu_model: dict[str, Any]
    ) -> None:
        _create_onu(real_client, chain["pon_port_id"], onu_model["onu_model_id"], onu_index=10)
        other = _create_onu(
            real_client, chain["pon_port_id"], onu_model["onu_model_id"], onu_index=11
        ).json()
        # Tenta mover 'other' para o índice 10 (já ocupado na mesma PON).
        resp = real_client.patch(
            f"/api/v1/onus/{other['onu_id']}",
            json={"onu_index": 10},
        )
        assert resp.status_code == 409

    def test_cannot_change_serial(
        self, real_client: Any, chain: dict[str, Any], onu_model: dict[str, Any]
    ) -> None:
        created = _create_onu(
            real_client,
            chain["pon_port_id"],
            onu_model["onu_model_id"],
            serial="IMMUTABLE001",
        ).json()
        # serial não está no schema de Update -> ignorado (extra='ignore').
        resp = real_client.patch(
            f"/api/v1/onus/{created['onu_id']}",
            json={"serial": "CHANGED999"},
        )
        assert resp.status_code == 200
        assert resp.json()["serial"] == "IMMUTABLE001"


class TestOnuSoftDelete:
    def test_soft_delete_returns_204(
        self, real_client: Any, chain: dict[str, Any], onu_model: dict[str, Any]
    ) -> None:
        created = _create_onu(real_client, chain["pon_port_id"], onu_model["onu_model_id"]).json()
        resp = real_client.delete(f"/api/v1/onus/{created['onu_id']}")
        assert resp.status_code == 204

    def test_soft_delete_then_get_returns_404(
        self, real_client: Any, chain: dict[str, Any], onu_model: dict[str, Any]
    ) -> None:
        created = _create_onu(real_client, chain["pon_port_id"], onu_model["onu_model_id"]).json()
        real_client.delete(f"/api/v1/onus/{created['onu_id']}")
        resp = real_client.get(f"/api/v1/onus/{created['onu_id']}")
        assert resp.status_code == 404

    def test_soft_delete_frees_serial(
        self, real_client: Any, chain: dict[str, Any], onu_model: dict[str, Any]
    ) -> None:
        serial = "REUSE0001"
        first = _create_onu(
            real_client, chain["pon_port_id"], onu_model["onu_model_id"], serial=serial
        ).json()
        real_client.delete(f"/api/v1/onus/{first['onu_id']}")
        # Mesmo serial pode ser recriado após soft delete (unicidade parcial).
        again = _create_onu(
            real_client, chain["pon_port_id"], onu_model["onu_model_id"], serial=serial
        )
        assert again.status_code == 201
        assert again.json()["onu_id"] != first["onu_id"]

    def test_soft_delete_frees_pon_index(
        self, real_client: Any, chain: dict[str, Any], onu_model: dict[str, Any]
    ) -> None:
        first = _create_onu(
            real_client, chain["pon_port_id"], onu_model["onu_model_id"], onu_index=15
        ).json()
        real_client.delete(f"/api/v1/onus/{first['onu_id']}")
        again = _create_onu(
            real_client, chain["pon_port_id"], onu_model["onu_model_id"], onu_index=15
        )
        assert again.status_code == 201
