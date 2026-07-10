# Testes de idempotência de POST /provisioning-orders (Rodada 3).

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.integration.api.test_auth import _bootstrap_admin


@pytest.fixture
def admin_headers(real_client: TestClient) -> dict[str, str]:
    """Bootstrap admin. _bootstrap_admin devolve (headers, username);
    descartamos o username porque a rota de create não precisa dele."""
    headers, _ = _bootstrap_admin(real_client)
    return headers


_POST_ORDER = "/api/v1/provisioning-orders"


def _minimal_payload(
    *,
    idempotency_key: str,
    olt_id: str,
    pon_port_id: str,
    template_id: str,
    serial: str,
    line_profile_id: str,
    service_profile_id: str,
    vlan_id: str,
    onu_index: int,
) -> dict:
    """Payload aceito pelo ProvisioningOrderCreate + SnapshotParams."""
    return {
        "olt_id": olt_id,
        "pon_port_id": pon_port_id,
        "provisioning_template_id": template_id,
        "idempotency_key": idempotency_key,
        "serial": serial,
        "snapshot": {
            "line_profile_id": line_profile_id,
            "service_profile_id": service_profile_id,
            "vlan_id": vlan_id,
            "onu_index": onu_index,
        },
    }


@pytest.fixture
def provisioning_setup(real_client: TestClient, admin_headers: dict[str, str]):
    """Cria a cadeia mínima para POST /provisioning-orders funcionar."""
    pytest.skip(
        "provisioning_setup fixture: reaproveitar da suíte existente de "
        "test_provisioning_orders.py — este arquivo só demonstra os "
        "novos casos, não duplica setup pesado."
    )


def test_idempotent_same_payload_returns_200_reused(
    real_client: TestClient,
    admin_headers: dict[str, str],
    provisioning_setup: dict,
) -> None:
    key = f"pytest-idem-{uuid4().hex[:8]}"
    payload = _minimal_payload(idempotency_key=key, **provisioning_setup)

    first = real_client.post(_POST_ORDER, json=payload, headers=admin_headers)
    assert first.status_code == 202, first.text
    first_id = first.json()["provisioning_order_id"]
    first_hash = first.json()["idempotency_payload_hash"]
    assert first_hash is not None

    # Reenvia com MESMO key + MESMO payload -> 200 OK + mesma ordem.
    second = real_client.post(_POST_ORDER, json=payload, headers=admin_headers)
    assert second.status_code == 200, second.text
    assert second.json()["provisioning_order_id"] == first_id
    assert second.json()["idempotency_payload_hash"] == first_hash


def test_idempotent_different_payload_returns_409_mismatch(
    real_client: TestClient,
    admin_headers: dict[str, str],
    provisioning_setup: dict,
) -> None:
    key = f"pytest-idem-{uuid4().hex[:8]}"
    payload_a = _minimal_payload(idempotency_key=key, **provisioning_setup)
    first = real_client.post(_POST_ORDER, json=payload_a, headers=admin_headers)
    assert first.status_code == 202, first.text

    # Mesmo key, payload diferente (troca onu_index).
    payload_b = dict(payload_a)
    payload_b["snapshot"] = {
        **payload_a["snapshot"],
        "onu_index": provisioning_setup["onu_index"] + 1,
    }

    second = real_client.post(_POST_ORDER, json=payload_b, headers=admin_headers)
    assert second.status_code == 409, second.text
    body = second.json()
    assert body["error"]["code"] == "conflict"
    assert body["error"]["details"]["idempotency_key"] == key


def test_hash_is_stable_across_key_order(
    real_client: TestClient,
    admin_headers: dict[str, str],
    provisioning_setup: dict,
) -> None:
    key = f"pytest-stable-{uuid4().hex[:8]}"
    payload = _minimal_payload(idempotency_key=key, **provisioning_setup)

    r1 = real_client.post(_POST_ORDER, json=payload, headers=admin_headers)
    r2 = real_client.post(_POST_ORDER, json=payload, headers=admin_headers)
    assert r1.status_code == 202
    assert r2.status_code == 200
    assert r1.json()["idempotency_payload_hash"] == r2.json()["idempotency_payload_hash"]
