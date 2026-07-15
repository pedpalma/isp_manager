# Testes de integração da instrumentação.

from __future__ import annotations

from datetime import datetime, timezone  # noqa: F401
from typing import Any
from uuid import UUID, uuid4

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text

from app.core.config import settings
from tests.integration.api.test_auth import (  # type: ignore
    _PASSWORD,  # noqa: F401
    _bootstrap_admin,
    _create_group,
    _create_user,
    _login,
    _sync_engine,
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
    assert row is not None, f"app_user não encontrado: {username}"
    return row[0]


def _fetch_audits_by_entity(entity_id: UUID) -> list[dict[str, Any]]:
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
                ORDER BY created_at ASC
                """
                ),
                {"eid": str(entity_id)},
            )
            .mappings()
            .all()
        )
    return [dict(r) for r in rows]


def _fetch_single_audit(entity_id: UUID, action: str) -> dict[str, Any]:
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
                WHERE entity_id = :eid AND action = :act
                ORDER BY created_at ASC
                """
                ),
                {"eid": str(entity_id), "act": action},
            )
            .mappings()
            .all()
        )
    assert len(rows) == 1, (
        f"esperado 1 audit_log para (entity_id={entity_id}, action={action}), achei {len(rows)}"
    )
    return dict(rows[0])


def test_login_records_audit(real_client: TestClient) -> None:
    _, admin_username = _bootstrap_admin(real_client)
    admin_id = _fetch_user_id_by_username(admin_username)

    row = _fetch_single_audit(admin_id, "auth.login")

    assert row["result"] == "success"
    assert row["entity_type"] == "app_user"
    assert row["entity_id"] == admin_id
    assert row["app_user_id"] == admin_id
    metadata = row["metadata"]
    assert metadata is not None
    assert metadata["actor_is_system"] is False
    assert metadata["actor_username"] == admin_username
    assert metadata.get("session_id")  # UUID string
    # request_id propagado pelo middleware
    assert row["request_id"]


def test_login_failure_does_not_record_audit(real_client: TestClient) -> None:
    """Senha errada => 401 e não grava audit (v1 audita só success)."""
    admin_headers, _ = _bootstrap_admin(real_client)
    group_id = _create_group(real_client, admin_headers)
    username, _ = _create_user(real_client, admin_headers, group_id)
    user_id = _fetch_user_id_by_username(username)

    # Tenta login com senha errada
    resp = real_client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "senha-errada-xxx"},
    )
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    # não pode existir audit_log de auth.login para esse user
    rows = _fetch_audits_by_entity(user_id)
    login_rows = [r for r in rows if r["action"] == "auth.login"]
    assert login_rows == []


def test_change_password_records_audit_without_leaking_password(
    real_client: TestClient,
) -> None:
    """change-password grava audit; NUNCA emite senha em nenhum campo."""
    admin_headers, _ = _bootstrap_admin(real_client)
    group_id = _create_group(real_client, admin_headers)
    username, password = _create_user(real_client, admin_headers, group_id)
    user_id = _fetch_user_id_by_username(username)

    user_headers = _login(real_client, username, password)

    resp = real_client.post(
        "/api/v1/auth/change-password",
        headers=user_headers,
        json={"current_password": password, "new_password": "novaSenha123"},
    )
    assert resp.status_code == status.HTTP_204_NO_CONTENT, resp.text

    row = _fetch_single_audit(user_id, "auth.password_changed")
    assert row["result"] == "success"
    assert row["app_user_id"] == user_id
    metadata = row["metadata"] or {}
    assert "password" not in metadata
    assert "new_password" not in metadata
    assert "current_password" not in metadata
    assert metadata.get("revoked_all_sessions") is True
    # before/after não devem carregar senha
    assert row["before_data"] is None or "password" not in row["before_data"]
    assert row["after_data"] is None or "password" not in row["after_data"]


def test_logout_records_audit(real_client: TestClient) -> None:
    admin_headers, admin_username = _bootstrap_admin(real_client)
    admin_id = _fetch_user_id_by_username(admin_username)

    resp = real_client.post("/api/v1/auth/logout", headers=admin_headers)
    assert resp.status_code == status.HTTP_204_NO_CONTENT

    # Existe pelo menos 1 audit_log de logout para esse user
    rows = _fetch_audits_by_entity(admin_id)
    logout_rows = [r for r in rows if r["action"] == "auth.logout"]
    assert len(logout_rows) == 1
    assert logout_rows[0]["result"] == "success"
    assert logout_rows[0]["app_user_id"] == admin_id
    assert (logout_rows[0]["metadata"] or {}).get("session_id")


def _create_olt_for_test(real_client: TestClient, headers: dict[str, str]) -> UUID:
    """Reusa setup_inventory para minimizar boilerplate."""
    from tests.integration.api._olt_mock import setup_inventory  # type: ignore

    inv = setup_inventory(real_client, headers)
    return UUID(str(inv["olt_id"]))


def test_create_discovery_job_records_audit(real_client: TestClient) -> None:
    admin_headers, _ = _bootstrap_admin(real_client)
    olt_id = _create_olt_for_test(real_client, admin_headers)

    resp = real_client.post(
        "/api/v1/collection-jobs",
        headers=admin_headers,
        json={"olt_id": str(olt_id)},
    )
    assert resp.status_code in (
        status.HTTP_201_CREATED,
        status.HTTP_202_ACCEPTED,
    ), resp.text
    job_id = UUID(resp.json()["collection_job_id"])

    row = _fetch_single_audit(job_id, "collection_job.created")
    assert row["result"] == "success"
    assert row["entity_type"] == "collection_job"
    assert row["olt_id"] == olt_id
    # inventory routes usam get_current_actor (system_actor); mas
    # collection-jobs usa require_admin? Aceita ambos:
    metadata = row["metadata"] or {}
    assert metadata.get("job_type") == "discovery"
    assert metadata.get("trigger_type") == "manual"


def test_create_signal_reading_job_records_audit(real_client: TestClient) -> None:
    admin_headers, _ = _bootstrap_admin(real_client)
    olt_id = _create_olt_for_test(real_client, admin_headers)

    resp = real_client.post(
        "/api/v1/collection-jobs/signal-reading",
        headers=admin_headers,
        json={"olt_id": str(olt_id)},
    )
    assert resp.status_code in (
        status.HTTP_201_CREATED,
        status.HTTP_202_ACCEPTED,
    ), resp.text
    job_id = UUID(resp.json()["collection_job_id"])

    row = _fetch_single_audit(job_id, "collection_job.created")
    assert row["result"] == "success"
    assert row["olt_id"] == olt_id
    assert (row["metadata"] or {}).get("job_type") == "signal_reading"


def test_create_provisioning_order_records_audit(real_client: TestClient) -> None:
    """Cria uma ordem via HTTP e verifica que o audit_log foi gravado."""
    from tests.integration.api._provisioning_setup import (  # type: ignore
        build_snapshot,
        seed_pending_onu,
        setup_full_provisioning_chain,
    )

    admin_headers, admin_username = _bootstrap_admin(real_client)
    admin_id = _fetch_user_id_by_username(admin_username)

    chain = setup_full_provisioning_chain(real_client, admin_headers)
    olt_id = UUID(str(chain["olt_id"]))
    pon_port_id = UUID(str(chain["pon_port_id"]))
    template_id = UUID(str(chain["provisioning_template_id"]))

    serial = f"PYTEST{uuid4().hex[:8].upper()}"
    seed_pending_onu(_sync_engine(), chain, serial=serial)

    snapshot = build_snapshot(chain)

    resp = real_client.post(
        "/api/v1/provisioning-orders",
        headers=admin_headers,
        json={
            "olt_id": str(olt_id),
            "pon_port_id": str(pon_port_id),
            "provisioning_template_id": str(template_id),
            "idempotency_key": _unique("prov"),
            "serial": serial,
            "snapshot": snapshot,
        },
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED, resp.text
    order_id = UUID(resp.json()["provisioning_order_id"])

    row = _fetch_single_audit(order_id, "provisioning_order.created")
    assert row["result"] == "success"
    assert row["entity_type"] == "provisioning_order"
    assert row["provisioning_order_id"] == order_id
    assert row["olt_id"] == olt_id
    assert row["app_user_id"] == admin_id
    metadata = row["metadata"] or {}
    assert metadata["actor_is_system"] is False
    assert metadata["actor_username"] == admin_username
    assert metadata.get("payload_hash")
    after = row["after_data"] or {}
    assert after.get("status") == "pending"
    assert after.get("serial") == serial


def test_cancel_provisioning_order_records_audit(real_client: TestClient) -> None:
    """Cria uma ordem e forca status=pending via SQL"""
    from tests.integration.api._provisioning_setup import (  # type: ignore
        build_snapshot,
        seed_pending_onu,
        setup_full_provisioning_chain,
    )

    admin_headers, admin_username = _bootstrap_admin(real_client)
    admin_id = _fetch_user_id_by_username(admin_username)

    chain = setup_full_provisioning_chain(real_client, admin_headers)
    olt_id = UUID(str(chain["olt_id"]))
    pon_port_id = UUID(str(chain["pon_port_id"]))
    template_id = UUID(str(chain["provisioning_template_id"]))

    serial = f"PYTEST{uuid4().hex[:8].upper()}"
    seed_pending_onu(_sync_engine(), chain, serial=serial)
    snapshot = build_snapshot(chain)

    resp = real_client.post(
        "/api/v1/provisioning-orders",
        headers=admin_headers,
        json={
            "olt_id": str(olt_id),
            "pon_port_id": str(pon_port_id),
            "provisioning_template_id": str(template_id),
            "idempotency_key": _unique("prov-cancel"),
            "serial": serial,
            "snapshot": snapshot,
        },
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED, resp.text
    order_id = UUID(resp.json()["provisioning_order_id"])

    # Forca status=pending para permitir cancel (Celery task_always_eager
    with _get_migrator_engine().begin() as conn:
        conn.execute(
            text(
                "UPDATE provisioning_order "
                "SET status='pending', finished_at=NULL, failure_reason=NULL "
                "WHERE provisioning_order_id = :pid"
            ),
            {"pid": str(order_id)},
        )

    # Cancel via HTTP
    resp = real_client.post(
        f"/api/v1/provisioning-orders/{order_id}/cancel",
        headers=admin_headers,
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text

    row = _fetch_single_audit(order_id, "provisioning_order.canceled")
    assert row["result"] == "success"
    assert row["app_user_id"] == admin_id
    assert row["provisioning_order_id"] == order_id
    assert (row["before_data"] or {}).get("status") == "pending"
    after = row["after_data"] or {}
    assert after.get("status") == "canceled"
    assert after.get("finished_at")


def _seed_optical_alert_event(
    onu_id: UUID,
    policy_id: UUID,
) -> UUID:
    """Insere um optical_alert_event em status='open' via migrator."""
    alert_id = uuid4()
    with _get_migrator_engine().begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO optical_alert_event (
                    optical_alert_event_id, onu_id, policy_id,
                    metric_name, value, status
                )
                VALUES (:id, :onu_id, :pid, :m, :v, 'open')
                """
            ),
            {
                "id": str(alert_id),
                "onu_id": str(onu_id),
                "pid": str(policy_id),
                "m": "rx_power_dbm",
                "v": -30.5,
            },
        )
    return alert_id


def _seed_optical_policy_and_onu(
    real_client: TestClient, headers: dict[str, str]
) -> tuple[UUID, UUID]:
    """Cria OLT+PON via setup_inventory (não cria ONU), cria onu_model +
    onu via API, e insere policy 'global' via SQL.
    Retorna (onu_id, policy_id)."""
    from tests.integration.api._olt_mock import setup_inventory  # type: ignore

    inv = setup_inventory(real_client, headers)

    r = real_client.post(
        "/api/v1/onu-models",
        headers=headers,
        json={
            "manufacturer_id": str(inv["manufacturer_id"]),
            "model": _unique("onum"),
            "active": True,
        },
    )
    assert r.status_code == status.HTTP_201_CREATED, r.text
    onu_model_id = r.json()["onu_model_id"]

    serial = f"PYTEST{uuid4().hex[:8].upper()}"
    r = real_client.post(
        "/api/v1/onus",
        headers=headers,
        json={
            "pon_port_id": str(inv["pon_port_id"]),
            "onu_model_id": onu_model_id,
            "serial": serial,
        },
    )
    assert r.status_code == status.HTTP_201_CREATED, r.text
    onu_id = UUID(r.json()["onu_id"])

    policy_id = uuid4()
    with _get_migrator_engine().begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO optical_threshold_policy (
                    optical_threshold_policy_id, scope_type,
                    metric_name, warning_threshold, critical_threshold,
                    severity, active
                )
                VALUES (:id, 'global', 'rx_power_dbm', -28.0, -32.0, 'critical', TRUE)
                """
            ),
            {"id": str(policy_id)},
        )
    return onu_id, policy_id


def test_acknowledge_alert_records_audit(real_client: TestClient) -> None:
    admin_headers, admin_username = _bootstrap_admin(real_client)
    admin_id = _fetch_user_id_by_username(admin_username)

    onu_id, policy_id = _seed_optical_policy_and_onu(real_client, admin_headers)
    alert_id = _seed_optical_alert_event(onu_id, policy_id)

    resp = real_client.post(
        f"/api/v1/optical-alerts/{alert_id}/acknowledge",
        headers=admin_headers,
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text

    row = _fetch_single_audit(alert_id, "optical_alert.acknowledged")
    assert row["result"] == "success"
    assert row["entity_type"] == "optical_alert_event"
    assert row["onu_id"] == onu_id
    assert row["app_user_id"] == admin_id
    assert (row["before_data"] or {}).get("status") == "open"
    assert (row["after_data"] or {}).get("status") == "acknowledged"


def test_acknowledge_already_acknowledged_does_not_record_new_audit(
    real_client: TestClient,
) -> None:
    admin_headers, _ = _bootstrap_admin(real_client)
    onu_id, policy_id = _seed_optical_policy_and_onu(real_client, admin_headers)
    alert_id = _seed_optical_alert_event(onu_id, policy_id)

    real_client.post(f"/api/v1/optical-alerts/{alert_id}/acknowledge", headers=admin_headers)
    real_client.post(f"/api/v1/optical-alerts/{alert_id}/acknowledge", headers=admin_headers)

    audits = _fetch_audits_by_entity(alert_id)
    ack_audits = [a for a in audits if a["action"] == "optical_alert.acknowledged"]
    assert len(ack_audits) == 1, (
        f"esperado 1 audit de ack (idempotência sem transição "
        f"não gera novo audit), achei {len(ack_audits)}"
    )
