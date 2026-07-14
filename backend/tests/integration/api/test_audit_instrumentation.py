from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text

from app.core.config import settings
from tests.integration.api._olt_mock import setup_inventory  # type: ignore
from tests.integration.api.test_auth import (  # type: ignore
    _bootstrap_admin,
    _unique,
)

_migrator_engine: Engine | None = None


def _get_migrator_engine() -> Engine:
    global _migrator_engine
    if _migrator_engine is None:
        _migrator_engine = create_engine(
            settings.database.build_migrator_url(),
            future=True,
        )
    return _migrator_engine


def _fetch_user_id_by_username(username: str) -> UUID:
    with _get_migrator_engine().begin() as conn:
        row = conn.execute(
            text("SELECT app_user_id FROM app_user WHERE username = :u"),
            {"u": username},
        ).first()
    assert row is not None, f"app_user nao encontrado: {username}"
    return row[0]


def _fetch_audit_by_entity(entity_id: UUID) -> dict[str, Any]:
    """Retorna o ÚNICO audit_log com esse entity_id. Falha se 0 ou >1."""
    with _get_migrator_engine().begin() as conn:
        rows = (
            conn.execute(
                text(
                    """
                SELECT audit_log_id, app_user_id, olt_id, onu_id,
                    provisioning_order_id, entity_type, entity_id,
                    action, result, error_detail,
                    before_data, after_data, metadata, request_id, created_at
                FROM audit_log
                WHERE entity_id = :eid
                ORDER BY created_at DESC
                """
                ),
                {"eid": str(entity_id)},
            )
            .mappings()
            .all()
        )
    assert len(rows) == 1, f"esperado 1 audit_log para entity_id={entity_id}, achei {len(rows)}"
    return dict(rows[0])


def test_olt_soft_delete_records_audit(real_client: TestClient) -> None:
    headers, admin_username = _bootstrap_admin(real_client)
    admin_id = _fetch_user_id_by_username(admin_username)

    inv = setup_inventory(real_client, headers)
    olt_id = UUID(inv["olt_id"])

    # act: soft-delete via API
    resp = real_client.delete(f"/api/v1/olts/{olt_id}", headers=headers)
    assert resp.status_code == status.HTTP_204_NO_CONTENT, resp.text

    # assert: audit_log gravado dentro da mesma TX
    row = _fetch_audit_by_entity(olt_id)
    assert row["action"] == "olt.soft_deleted"
    assert row["result"] == "success"
    assert row["entity_type"] == "olt"
    assert row["entity_id"] == olt_id
    assert row["olt_id"] == olt_id
    assert row["app_user_id"] == admin_id
    # metadata do audit
    assert row["metadata"]["actor_is_system"] is False
    assert row["metadata"]["actor_username"] == admin_username
    assert row["metadata"]["name"]  # nome da OLT preservado como contexto
    # request_id propagado pelo middleware
    assert row["request_id"] is not None
    assert len(row["request_id"]) > 0
    # payload de mutação
    assert row["before_data"] == {"deleted_at": None}
    assert row["after_data"]["deleted_at"] is not None


def test_olt_soft_delete_of_missing_olt_does_not_record_audit(
    real_client: TestClient,
) -> None:
    """404 no soft_delete NAO deve gerar audit_log (auditamos SO SUCCESS na v1)."""
    headers, _ = _bootstrap_admin(real_client)
    ghost = UUID("00000000-0000-0000-0000-000000000000")

    resp = real_client.delete(f"/api/v1/olts/{ghost}", headers=headers)
    assert resp.status_code == status.HTTP_404_NOT_FOUND

    with _get_migrator_engine().begin() as conn:
        row = conn.execute(
            text("SELECT COUNT(*) FROM audit_log WHERE entity_id = :eid"),
            {"eid": str(ghost)},
        ).first()
    assert row is not None
    assert row[0] == 0


def _create_credential_via_api(
    real_client: TestClient,
    headers: dict[str, str],
    *,
    label: str,
    secret_ref: str,
    enable_secret_ref: str | None = None,
    private_key_ref: str | None = None,
    auth_type: str = "password",
) -> UUID:
    payload: dict[str, Any] = {
        "label": label,
        "username": "netadmin",
        "secret_ref": secret_ref,
        "auth_type": auth_type,
        "active": True,
    }
    if enable_secret_ref is not None:
        payload["enable_secret_ref"] = enable_secret_ref
    if private_key_ref is not None:
        payload["private_key_ref"] = private_key_ref

    resp = real_client.post("/api/v1/credentials", headers=headers, json=payload)
    assert resp.status_code == status.HTTP_201_CREATED, resp.text
    return UUID(resp.json()["credential_id"])


def test_create_credential_records_audit_masks_secret_pointers(
    real_client: TestClient,
) -> None:
    headers, admin_username = _bootstrap_admin(real_client)
    admin_id = _fetch_user_id_by_username(admin_username)

    label = _unique("cred-create")
    cred_id = _create_credential_via_api(
        real_client,
        headers,
        label=label,
        secret_ref="OLT_ADMIN_PASSWORD_REF",
        enable_secret_ref="ENABLE_SECRET_REF_HERE",
    )

    row = _fetch_audit_by_entity(cred_id)
    assert row["action"] == "credential.created"
    assert row["result"] == "success"
    assert row["entity_type"] == "credential"
    assert row["app_user_id"] == admin_id
    assert row["olt_id"] is None  # credential nao vive sob uma OLT

    after = row["after_data"]
    # Campos NAO sensíveis: legíveis
    assert after["label"] == label
    assert after["username"] == "netadmin"
    assert after["auth_type"] == "password"
    assert after["active"] is True
    # Ponteiros de secret: MASCARADOS
    assert after["secret_ref"] == "***"
    assert after["enable_secret_ref"] == "***"


def test_update_credential_records_audit_masks_secret_pointers(
    real_client: TestClient,
) -> None:
    headers, admin_username = _bootstrap_admin(real_client)
    admin_id = _fetch_user_id_by_username(admin_username)

    # cria uma credencial (isso ja gera 1 audit_log de credential.created)
    label_old = _unique("cred-update-old")
    cred_id = _create_credential_via_api(
        real_client,
        headers,
        label=label_old,
        secret_ref="OLD_SECRET_REF",
    )

    # atualiza label + secret_ref
    label_new = _unique("cred-update-new")
    resp = real_client.patch(
        f"/api/v1/credentials/{cred_id}",
        headers=headers,
        json={"label": label_new, "secret_ref": "NEW_SECRET_REF"},
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text

    # Agora existem 2 audit_logs para esse entity_id (created + updated).
    with _get_migrator_engine().begin() as conn:
        rows = (
            conn.execute(
                text(
                    """
                SELECT action, result, before_data, after_data,
                    app_user_id, request_id, metadata
                FROM audit_log
                WHERE entity_id = :eid
                ORDER BY created_at ASC
                """
                ),
                {"eid": str(cred_id)},
            )
            .mappings()
            .all()
        )
    assert len(rows) == 2
    assert rows[0]["action"] == "credential.created"
    updated = rows[1]

    assert updated["action"] == "credential.updated"
    assert updated["result"] == "success"
    assert updated["app_user_id"] == admin_id

    # before: SOMENTE campos tocados, com secret_ref mascarado
    assert updated["before_data"] == {
        "label": label_old,
        "secret_ref": "***",
    }
    # after: SOMENTE campos tocados, com secret_ref mascarado
    assert updated["after_data"] == {
        "label": label_new,
        "secret_ref": "***",
    }
