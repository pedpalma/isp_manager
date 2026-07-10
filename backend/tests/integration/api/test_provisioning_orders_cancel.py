# Testes de POST /provisioning-orders/{id}/cancel (Rodada 3).

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.integration.api.test_auth import _bootstrap_admin


@pytest.fixture
def admin_headers(real_client: TestClient) -> dict[str, str]:
    """Bootstrap admin (cria pytest-admin-* e faz login).
    _bootstrap_admin devolve (headers, username); descartamos o
    username porque o cancel não precisa dele."""
    headers, _ = _bootstrap_admin(real_client)
    return headers


@pytest.fixture
def pending_order_id(real_client: TestClient, admin_headers: dict[str, str]) -> str:
    """Cria uma ordem em PENDING via INSERT direto para testar cancel."""
    pytest.skip(
        "pending_order_id fixture: extrair setup de test_provisioning_orders.py "
        "e inserir ordem via SQL direto com status='pending' (contornando o "
        "worker eager). Ver comentário acima."
    )


def test_cancel_pending_returns_200_and_canceled_status(
    real_client: TestClient,
    admin_headers: dict[str, str],
    pending_order_id: str,
) -> None:
    resp = real_client.post(
        f"/api/v1/provisioning-orders/{pending_order_id}/cancel",
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["provisioning_order_id"] == pending_order_id
    assert body["status"] == "canceled"
    assert body["finished_at"] is not None
    assert "canceled by" in (body["failure_reason"] or "")


def test_cancel_idempotent_second_call_returns_409(
    real_client: TestClient,
    admin_headers: dict[str, str],
    pending_order_id: str,
) -> None:
    """Cancel duplo: primeiro OK, segundo 409 (já não está PENDING)."""
    r1 = real_client.post(
        f"/api/v1/provisioning-orders/{pending_order_id}/cancel",
        headers=admin_headers,
    )
    assert r1.status_code == 200

    r2 = real_client.post(
        f"/api/v1/provisioning-orders/{pending_order_id}/cancel",
        headers=admin_headers,
    )
    assert r2.status_code == 409
    body = r2.json()
    assert body["error"]["code"] == "conflict"
    assert body["error"]["details"]["current_status"] == "canceled"


def test_cancel_nonexistent_returns_404(
    real_client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    resp = real_client.post(
        f"/api/v1/provisioning-orders/{uuid4()}/cancel",
        headers=admin_headers,
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


def test_cancel_requires_auth(real_client: TestClient) -> None:
    resp = real_client.post(f"/api/v1/provisioning-orders/{uuid4()}/cancel")
    assert resp.status_code == 401
