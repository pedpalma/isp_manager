# Testes de integração da instrumentação de audit_log nos workers
# síncronos (provisioning e discovery). Sob Celery task_always_eager=True
# (fixture do conftest), o worker roda sync ao retornar do POST HTTP,
# então os audits do worker já estão gravados quando o cliente recebe a
# resposta.

from __future__ import annotations

import os
from typing import Any
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text

from app.core.config import settings
from tests.integration.api.test_auth import (  # type: ignore
    _bootstrap_admin,
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


def _fetch_audits(entity_id: UUID, action: str) -> list[dict[str, Any]]:
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
    return [dict(r) for r in rows]


def _ensure_secret_env() -> None:
    os.environ.setdefault("PYTEST_OLT_SECRET", "pytest-fake-pass")


def _create_olt_for_test(real_client: TestClient, headers: dict[str, str]) -> UUID:
    from tests.integration.api._olt_mock import setup_inventory  # type: ignore

    inv = setup_inventory(real_client, headers)
    return UUID(str(inv["olt_id"]))


# Provisioning worker
def test_provisioning_success_records_started_and_finished(
    real_client: TestClient,
) -> None:
    """Happy path: canned success default => STARTED + FINISHED/SUCCESS.

    Combinado com o audit CREATED que já vem do service, a ordem terá 3
    audits ao final (created, started, finished). Só verificamos os 2 do
    worker aqui; o CREATED já é coberto pela suíte de instrumentação do
    service.
    """
    from tests.integration.api._provisioning_setup import (  # type: ignore
        build_snapshot,
        seed_pending_onu,
        setup_full_provisioning_chain,
    )

    _ensure_secret_env()
    admin_headers, admin_username = _bootstrap_admin(real_client)
    admin_id = _fetch_user_id_by_username(admin_username)

    chain = setup_full_provisioning_chain(real_client, admin_headers)
    olt_id = UUID(str(chain["olt_id"]))

    serial = f"PYTST{uuid4().hex[:8].upper()}"
    engine = _sync_engine()
    try:
        seed_pending_onu(engine, chain, serial=serial)
    finally:
        engine.dispose()

    body = {
        "olt_id": str(chain["olt_id"]),
        "pon_port_id": str(chain["pon_port_id"]),
        "serial": serial,
        "provisioning_template_id": str(chain["provisioning_template_id"]),
        "idempotency_key": _unique("prov-ok"),
        "snapshot": build_snapshot(chain),
    }
    r = real_client.post("/api/v1/provisioning-orders", headers=admin_headers, json=body)
    assert r.status_code == 202, r.text
    assert r.json()["status"] == "success"
    order_id = UUID(r.json()["provisioning_order_id"])

    # STARTED: transição validating -> running gravada pelo worker
    started = _fetch_audits(order_id, "provisioning_order.started")
    assert len(started) == 1, f"esperado 1 audit STARTED, achei {len(started)}"
    row = started[0]
    assert row["result"] == "success"
    assert row["entity_type"] == "provisioning_order"
    assert row["entity_id"] == order_id
    assert row["provisioning_order_id"] == order_id
    assert row["olt_id"] == olt_id
    assert row["app_user_id"] == admin_id
    assert (row["after_data"] or {}).get("status") == "running"
    metadata = row["metadata"] or {}
    assert metadata.get("actor_is_system") is False
    assert metadata.get("actor_username") == admin_username
    assert row["request_id"]

    # FINISHED: transição para status terminal SUCCESS
    finished = _fetch_audits(order_id, "provisioning_order.finished")
    assert len(finished) == 1, f"esperado 1 audit FINISHED, achei {len(finished)}"
    row = finished[0]
    assert row["result"] == "success"
    assert row["entity_id"] == order_id
    assert row["provisioning_order_id"] == order_id
    assert row["olt_id"] == olt_id
    assert row["app_user_id"] == admin_id
    assert (row["after_data"] or {}).get("status") == "success"
    metadata = row["metadata"] or {}
    assert metadata.get("actor_is_system") is False
    assert metadata.get("actor_username") == admin_username


def test_provisioning_failure_records_started_and_terminal_audit(
    real_client: TestClient,
) -> None:
    """Canned failed com 1 step => sem rollback, ordem termina em FAILED
    (ou rolled_back/partial dependendo da semântica do mock).

    O que precisamos garantir: STARTED sempre existe (worker chegou a
    marcar RUNNING) e existe exatamente 1 audit terminal, com result
    espelhando o desfecho real.
    """
    from tests.integration.api._olt_mock import (  # type: ignore
        clear_canned_provisioning,
        set_canned_provisioning,
    )
    from tests.integration.api._provisioning_setup import (  # type: ignore
        build_snapshot,
        seed_pending_onu,
        setup_full_provisioning_chain,
    )

    _ensure_secret_env()
    admin_headers, admin_username = _bootstrap_admin(real_client)
    admin_id = _fetch_user_id_by_username(admin_username)

    chain = setup_full_provisioning_chain(real_client, admin_headers)

    serial = f"PYTFA{uuid4().hex[:8].upper()}"
    engine = _sync_engine()
    try:
        seed_pending_onu(engine, chain, serial=serial)
    finally:
        engine.dispose()

    set_canned_provisioning(
        chain["olt_id"],
        steps=[
            {
                "command_sent": "echo pytest-authorize_onu",
                "output_received": "ERROR: fake failure",
                "success": False,
                "duration_ms": 12,
            }
        ],
        overall_success=False,
    )
    try:
        body = {
            "olt_id": str(chain["olt_id"]),
            "pon_port_id": str(chain["pon_port_id"]),
            "serial": serial,
            "provisioning_template_id": str(chain["provisioning_template_id"]),
            "idempotency_key": _unique("prov-fail"),
            "snapshot": build_snapshot(chain),
        }
        r = real_client.post("/api/v1/provisioning-orders", headers=admin_headers, json=body)
        assert r.status_code == 202, r.text
        order_id = UUID(r.json()["provisioning_order_id"])
        final_status = r.json()["status"]
        assert final_status in ("failed", "rolled_back", "partial")
    finally:
        clear_canned_provisioning(chain["olt_id"])

    # STARTED sempre gravado antes do desfecho
    started = _fetch_audits(order_id, "provisioning_order.started")
    assert len(started) == 1
    assert started[0]["app_user_id"] == admin_id
    assert (started[0]["after_data"] or {}).get("status") == "running"

    # Audit terminal: rolled_back tem ação própria; failed/partial usam FINISHED
    if final_status == "rolled_back":
        rolled = _fetch_audits(order_id, "provisioning_order.rolled_back")
        assert len(rolled) == 1
        assert rolled[0]["result"] == "success"
        assert rolled[0]["app_user_id"] == admin_id
        assert (rolled[0]["after_data"] or {}).get("status") == "rolled_back"
    else:
        finished = _fetch_audits(order_id, "provisioning_order.finished")
        assert len(finished) == 1
        expected_result = "failure" if final_status == "failed" else "partial"
        assert finished[0]["result"] == expected_result
        assert finished[0]["app_user_id"] == admin_id
        assert finished[0]["error_detail"]  # falha carrega mensagem
        assert (finished[0]["after_data"] or {}).get("status") == final_status


# Discovery worker
def test_discovery_success_records_finished(real_client: TestClient) -> None:
    """Job manual disparado pela rota /collection-jobs grava
    COLLECTION_JOB_FINISHED via worker, com entity refs, olt_id, status
    coerente e request_id propagado.

    Sobre o actor: hoje a rota /collection-jobs injeta o Actor via
    get_current_actor, que devolve system_actor() mesmo em contexto
    autenticado (mesmo comportamento observado nos testes de audit do
    sistema). Consequentemente, requested_by_user_id do job fica NULL e
    o helper do worker cai no fallback documentado (system_actor()).
    A instrumentação está correta nesse cenário; o teste apenas confirma
    a coerência ponta-a-ponta e não fixa quem é o ator.

    TODO: quando get_current_actor passar a devolver ator humano em rota
    autenticada, apertar este teste para exigir app_user_id == admin_id
    e actor_is_system False.
    """
    _ensure_secret_env()
    admin_headers, _ = _bootstrap_admin(real_client)
    olt_id = _create_olt_for_test(real_client, admin_headers)

    r = real_client.post(
        "/api/v1/collection-jobs",
        headers=admin_headers,
        json={"olt_id": str(olt_id)},
    )
    assert r.status_code in (201, 202), r.text
    job_id = UUID(r.json()["collection_job_id"])

    finished = _fetch_audits(job_id, "collection_job.finished")
    assert len(finished) == 1, f"esperado 1 audit FINISHED, achei {len(finished)}"
    row = finished[0]
    # canned default do mock retorna success (ou partial se houver unmapped)
    assert row["result"] in ("success", "partial")
    assert row["entity_type"] == "collection_job"
    assert row["entity_id"] == job_id
    assert row["olt_id"] == olt_id
    assert (row["after_data"] or {}).get("status") in ("success", "partial")
    assert row["request_id"]
    # Metadata sempre carrega info de actor, seja ele humano ou system.
    metadata = row["metadata"] or {}
    assert "actor_is_system" in metadata
    assert metadata.get("actor_username")


# TODO: cobrir job de discovery com requested_by_user_id NULL (fluxo do
# Celery beat) => audit deve gravar app_user_id NULL + actor_is_system
# True. Exige chamar run_discovery_job_sync direto, fora do fluxo eager
# da rota HTTP; deixado para próxima rodada.

# TODO: cobrir rollback OK isolado (STARTED + ROLLED_BACK/SUCCESS) com
# template multi-step + canned mix (primeiro step sucesso, segundo
# falha). Hoje o cenário rolled_back é aceito no teste de falha via
# assert-in; caso operação passe a exigir template multi-step de
# verdade, o teste dedicado entra.
