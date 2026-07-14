# Testes de integração da rota /audit-log.

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text

from app.core.config import settings

# Helpers ja expostos por test_auth.
from tests.integration.api.test_auth import (  # type: ignore
    _bootstrap_admin,
    _create_group,
    _create_user,
    _login,
    _unique,
)

# infra: sync engine do migrator (bypass do REVOKE)

_migrator_engine: Engine | None = None


def _get_migrator_engine() -> Engine:
    global _migrator_engine
    if _migrator_engine is None:
        _migrator_engine = create_engine(
            settings.database.build_migrator_url(),
            future=True,
        )
    return _migrator_engine


def _delete_pytest_audit_logs() -> None:
    """Remove audit_logs de teste (entity_type LIKE 'pytest-%')."""
    with _get_migrator_engine().begin() as conn:
        conn.execute(text("DELETE FROM audit_log WHERE entity_type LIKE 'pytest-%'"))


def _insert_audit_log(
    *,
    entity_type: str,
    entity_id: UUID | None = None,
    action: str = "olt.soft_deleted",
    result: str = "success",
    app_user_id: UUID | None = None,
    olt_id: UUID | None = None,
    onu_id: UUID | None = None,
    provisioning_order_id: UUID | None = None,
    error_detail: str | None = None,
    request_id: str | None = None,
    event_metadata: dict[str, Any] | None = None,
    before_data: dict[str, Any] | None = None,
    after_data: dict[str, Any] | None = None,
    created_at: datetime | None = None,
) -> UUID:
    """Insere um audit_log via role migrator. Retorna o audit_log_id."""
    import json

    audit_log_id = uuid4()
    if entity_id is None:
        entity_id = uuid4()

    params: dict[str, Any] = {
        "id": str(audit_log_id),
        "app_user_id": str(app_user_id) if app_user_id else None,
        "olt_id": str(olt_id) if olt_id else None,
        "onu_id": str(onu_id) if onu_id else None,
        "prov_id": str(provisioning_order_id) if provisioning_order_id else None,
        "entity_type": entity_type,
        "entity_id": str(entity_id),
        "action": action,
        "result": result,
        "error_detail": error_detail,
        "before_data": json.dumps(before_data) if before_data is not None else None,
        "after_data": json.dumps(after_data) if after_data is not None else None,
        "event_metadata": json.dumps(event_metadata) if event_metadata is not None else None,
        "request_id": request_id,
    }

    if created_at is not None:
        sql = text(
            """
            INSERT INTO audit_log (
                audit_log_id, app_user_id, olt_id, onu_id, provisioning_order_id,
                entity_type, entity_id, action, result, error_detail,
                before_data, after_data, metadata, request_id, created_at
            )
            VALUES (
                :id, :app_user_id, :olt_id, :onu_id, :prov_id,
                :entity_type, :entity_id, :action, :result, :error_detail,
                CAST(:before_data AS JSONB), CAST(:after_data AS JSONB),
                CAST(:event_metadata AS JSONB), :request_id, :created_at
            )
            """
        )
        params["created_at"] = created_at
    else:
        sql = text(
            """
            INSERT INTO audit_log (
                audit_log_id, app_user_id, olt_id, onu_id, provisioning_order_id,
                entity_type, entity_id, action, result, error_detail,
                before_data, after_data, metadata, request_id
            )
            VALUES (
                :id, :app_user_id, :olt_id, :onu_id, :prov_id,
                :entity_type, :entity_id, :action, :result, :error_detail,
                CAST(:before_data AS JSONB), CAST(:after_data AS JSONB),
                CAST(:event_metadata AS JSONB), :request_id
            )
            """
        )

    with _get_migrator_engine().begin() as conn:
        conn.execute(sql, params)

    return audit_log_id


# Fixtures
@pytest.fixture(scope="module", autouse=True)
def _clean_audit_around_module():
    """Zera audit_logs de teste antes e depois do modulo."""
    _delete_pytest_audit_logs()
    yield
    _delete_pytest_audit_logs()


@pytest.fixture
def admin_headers(real_client: TestClient) -> dict[str, str]:
    """Cria admin pytest-* e devolve headers com Bearer token."""
    headers, _ = _bootstrap_admin(real_client)
    return headers


# Casos
def test_list_empty_returns_200_and_zero_total(
    real_client: TestClient, admin_headers: dict[str, str]
) -> None:
    _delete_pytest_audit_logs()

    resp = real_client.get(
        "/api/v1/audit-log",
        headers=admin_headers,
        params={"entity_type": "pytest-empty"},
    )
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["total"] == 0
    assert body["items"] == []


def test_list_returns_seeded_entries_ordered_by_created_desc(
    real_client: TestClient, admin_headers: dict[str, str]
) -> None:
    _delete_pytest_audit_logs()
    entity_type = _unique("list")

    # Faz seed em três registros com created_at explicito para ordenar.
    now = datetime.now(tz=timezone.utc)  # noqa: UP017
    older_id = _insert_audit_log(
        entity_type=entity_type,
        action="olt.soft_deleted",
        result="success",
        created_at=now - timedelta(minutes=10),
    )
    middle_id = _insert_audit_log(
        entity_type=entity_type,
        action="olt.soft_deleted",
        result="success",
        created_at=now - timedelta(minutes=5),
    )
    newest_id = _insert_audit_log(
        entity_type=entity_type,
        action="olt.soft_deleted",
        result="success",
        created_at=now,
    )

    resp = real_client.get(
        "/api/v1/audit-log",
        headers=admin_headers,
        params={"entity_type": entity_type, "page_size": 10},
    )
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["total"] == 3
    ids = [item["audit_log_id"] for item in body["items"]]
    assert ids == [str(newest_id), str(middle_id), str(older_id)]


def test_list_filter_by_action(real_client: TestClient, admin_headers: dict[str, str]) -> None:
    _delete_pytest_audit_logs()
    entity_type = _unique("filter-action")

    _insert_audit_log(entity_type=entity_type, action="olt.soft_deleted")
    _insert_audit_log(entity_type=entity_type, action="credential.created")
    _insert_audit_log(entity_type=entity_type, action="credential.created")

    resp = real_client.get(
        "/api/v1/audit-log",
        headers=admin_headers,
        params={"entity_type": entity_type, "action": "credential.created"},
    )
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["total"] == 2
    assert all(item["action"] == "credential.created" for item in body["items"])


def test_list_filter_by_result(real_client: TestClient, admin_headers: dict[str, str]) -> None:
    _delete_pytest_audit_logs()
    entity_type = _unique("filter-result")

    _insert_audit_log(entity_type=entity_type, result="success")
    _insert_audit_log(entity_type=entity_type, result="failure")

    resp = real_client.get(
        "/api/v1/audit-log",
        headers=admin_headers,
        params={"entity_type": entity_type, "result": "failure"},
    )
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["result"] == "failure"


def test_list_filter_by_request_id(real_client: TestClient, admin_headers: dict[str, str]) -> None:
    _delete_pytest_audit_logs()
    entity_type = _unique("filter-req")
    req_id = _unique("rid")

    _insert_audit_log(entity_type=entity_type, request_id=req_id)
    _insert_audit_log(entity_type=entity_type, request_id="other-req")

    resp = real_client.get(
        "/api/v1/audit-log",
        headers=admin_headers,
        params={"entity_type": entity_type, "request_id": req_id},
    )
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["request_id"] == req_id


def test_list_filter_by_created_range(
    real_client: TestClient, admin_headers: dict[str, str]
) -> None:
    _delete_pytest_audit_logs()
    entity_type = _unique("filter-range")
    base = datetime.now(tz=timezone.utc)  # noqa: UP017

    _insert_audit_log(entity_type=entity_type, created_at=base - timedelta(hours=2))
    _insert_audit_log(entity_type=entity_type, created_at=base - timedelta(minutes=30))
    _insert_audit_log(entity_type=entity_type, created_at=base)

    frm = (base - timedelta(hours=1)).isoformat()
    to = (base + timedelta(minutes=1)).isoformat()
    resp = real_client.get(
        "/api/v1/audit-log",
        headers=admin_headers,
        params={"entity_type": entity_type, "created_from": frm, "created_to": to},
    )
    body = resp.json()
    assert body["total"] == 2


def test_get_detail_returns_200(real_client: TestClient, admin_headers: dict[str, str]) -> None:
    entity_type = _unique("detail")
    audit_id = _insert_audit_log(
        entity_type=entity_type,
        action="credential.updated",
        before_data={"secret_ref": "OLD"},
        after_data={"secret_ref": "NEW"},
        event_metadata={"actor_username": "pytest-x", "actor_is_system": False},
    )

    resp = real_client.get(
        f"/api/v1/audit-log/{audit_id}",
        headers=admin_headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["audit_log_id"] == str(audit_id)
    assert body["action"] == "credential.updated"
    # JSONBs voltam como dict; nome Python e event_metadata (ver docstring do model).
    assert body["before_data"] == {"secret_ref": "OLD"}
    assert body["after_data"] == {"secret_ref": "NEW"}
    assert body["event_metadata"]["actor_username"] == "pytest-x"


def test_get_detail_404(real_client: TestClient, admin_headers: dict[str, str]) -> None:
    ghost = uuid4()
    resp = real_client.get(
        f"/api/v1/audit-log/{ghost}",
        headers=admin_headers,
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    body = resp.json()
    assert body["error"]["code"] == "not_found"


def test_list_requires_auth(real_client: TestClient) -> None:
    resp = real_client.get("/api/v1/audit-log")
    # HTTPBearer(auto_error=False) + require_admin -> InvalidToken (401).
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_list_requires_admin(real_client: TestClient) -> None:
    """Usuário em grupo sem {'all': True} recebe 403."""
    admin_headers_local, _ = _bootstrap_admin(real_client)
    group_id = _create_group(real_client, admin_headers_local, permissions={})
    username, password = _create_user(real_client, admin_headers_local, group_id)
    headers = _login(real_client, username, password)

    resp = real_client.get("/api/v1/audit-log", headers=headers)
    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_get_detail_requires_auth(real_client: TestClient) -> None:
    resp = real_client.get(f"/api/v1/audit-log/{uuid4()}")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_list_pagination(real_client: TestClient, admin_headers: dict[str, str]) -> None:
    _delete_pytest_audit_logs()
    entity_type = _unique("page")
    now = datetime.now(tz=timezone.utc)  # noqa: UP017

    # 5 registros com created_at determinísticos.
    for i in range(5):
        _insert_audit_log(
            entity_type=entity_type,
            action="olt.soft_deleted",
            created_at=now - timedelta(minutes=i),
        )

    resp1 = real_client.get(
        "/api/v1/audit-log",
        headers=admin_headers,
        params={"entity_type": entity_type, "page": 1, "page_size": 2},
    )
    body1 = resp1.json()
    assert body1["total"] == 5
    assert len(body1["items"]) == 2
    assert body1["has_next"] is True
    assert body1["has_prev"] is False

    resp3 = real_client.get(
        "/api/v1/audit-log",
        headers=admin_headers,
        params={"entity_type": entity_type, "page": 3, "page_size": 2},
    )
    body3 = resp3.json()
    assert len(body3["items"]) == 1
    assert body3["has_next"] is False
    assert body3["has_prev"] is True
