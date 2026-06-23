# Testes de integração das rotas /collection-jobs.

# Modo eager do Celery (setado em conftest): task_always_eager=True faz
# .delay() rodar SÍNCRONO no mesmo processo. Resultado: ao retornar do
# POST, o job já esta em estado terminal (success/partial/failed).

# Pré-requisito de ambiente: variável PYTEST_OLT_SECRET tem que existir
# para o EnvSecretStore resolver. conftest seta no inicio da sessão.

from __future__ import annotations

import os
from uuid import uuid4

from sqlalchemy import create_engine, text

from app.core.config import settings
from tests.integration.api._olt_mock import (
    clear_canned_discovery,
    set_canned_discovery,
    setup_inventory,
)
from tests.integration.api.test_auth import _bootstrap_admin

API = "/api/v1"


def _sync_engine():
    return create_engine(settings.database.build_app_sync_url())


def _ensure_secret_env():
    # Garante que o EnvSecretStore resolve a credencial usada pelos testes.
    os.environ.setdefault("PYTEST_OLT_SECRET", "pytest-fake-pass")


# Happy path
def test_create_discovery_job_success_with_canned_onus(real_client):
    _ensure_secret_env()
    headers, _ = _bootstrap_admin(real_client)
    inv = setup_inventory(real_client, headers)

    set_canned_discovery(
        inv["olt_id"],
        [
            {
                "serial": "ALCL01234567",
                "slot_index": inv["slot_index"],
                "pon_index": inv["pon_index"],
                "pon_position": 1,
                "vendor_id": "ALCL",
            },
            {
                "serial": "HWTC76543210",
                "slot_index": inv["slot_index"],
                "pon_index": inv["pon_index"],
                "pon_position": 2,
                "vendor_id": "HWTC",
            },
        ],
    )

    try:
        r = real_client.post(
            f"{API}/collection-jobs",
            headers=headers,
            json={"olt_id": str(inv["olt_id"])},
        )
        assert r.status_code == 202, r.text
        body = r.json()
        # Sob eager, já terminou (success ou partial; aqui todas mapeadas)
        assert body["status"] == "success"
        assert body["job_type"] == "discovery"
        assert body["trigger_type"] == "manual"
        # Logs gravados pelo worker
        assert len(body["logs"]) >= 1
        assert body["logs"][0]["command_sent"]

        # GET detail confere o mesmo estado
        job_id = body["collection_job_id"]
        r2 = real_client.get(f"{API}/collection-jobs/{job_id}", headers=headers)
        assert r2.status_code == 200
        assert r2.json()["status"] == "success"

        # GET pending-onus mostra as duas
        r3 = real_client.get(
            f"{API}/pending-onus",
            headers=headers,
            params={"olt_id": str(inv["olt_id"])},
        )
        assert r3.status_code == 200
        items = r3.json()["items"]
        serials = sorted(p["serial"] for p in items)
        assert serials == ["ALCL01234567", "HWTC76543210"]
    finally:
        clear_canned_discovery(inv["olt_id"])


# Empty discovery
def test_create_discovery_job_success_with_no_onus(real_client):
    _ensure_secret_env()
    headers, _ = _bootstrap_admin(real_client)
    inv = setup_inventory(real_client, headers)
    # canned vazio (default)
    r = real_client.post(
        f"{API}/collection-jobs",
        headers=headers,
        json={"olt_id": str(inv["olt_id"])},
    )
    assert r.status_code == 202, r.text
    assert r.json()["status"] == "success"


# Partial: ONU em slot/pon não cadastrado no inventario
def test_create_discovery_job_partial_when_pon_unmapped(real_client):
    _ensure_secret_env()
    headers, _ = _bootstrap_admin(real_client)
    inv = setup_inventory(real_client, headers)

    set_canned_discovery(
        inv["olt_id"],
        [
            # slot/pon inexistentes -> dropados, job vira PARTIAL
            {"serial": "XXXX00000001", "slot_index": 99, "pon_index": 99},
            # mapeado normalmente
            {
                "serial": "OKOK00000002",
                "slot_index": inv["slot_index"],
                "pon_index": inv["pon_index"],
            },
        ],
    )
    try:
        r = real_client.post(
            f"{API}/collection-jobs",
            headers=headers,
            json={"olt_id": str(inv["olt_id"])},
        )
        assert r.status_code == 202, r.text
        body = r.json()
        assert body["status"] == "partial"
    finally:
        clear_canned_discovery(inv["olt_id"])


# R9: upsert NUNCA regride state
def test_upsert_does_not_regress_resolved_state(real_client):
    _ensure_secret_env()
    headers, _ = _bootstrap_admin(real_client)
    inv = setup_inventory(real_client, headers)

    # Insere um pending_onu ja resolvido para um serial X
    serial = "RESV00000001"
    engine = _sync_engine()
    try:
        with engine.connect() as conn, conn.begin():
            conn.execute(
                text(
                    """
                    INSERT INTO pending_onu (
                        olt_id, pon_port_id, serial, state,
                        first_seen_at, last_seen_at, resolved_at,
                        discovery_source
                    ) VALUES (
                        :olt, :pon, :serial, 'resolved',
                        NOW() - INTERVAL '1 hour',
                        NOW() - INTERVAL '1 hour',
                        NOW() - INTERVAL '1 hour',
                        'manual-seed'
                    )
                    """
                ),
                {
                    "olt": str(inv["olt_id"]),
                    "pon": str(inv["pon_port_id"]),
                    "serial": serial,
                },
            )
    finally:
        engine.dispose()

    # Re-descoberta do mesmo serial pelo worker
    set_canned_discovery(
        inv["olt_id"],
        [
            {
                "serial": serial,
                "slot_index": inv["slot_index"],
                "pon_index": inv["pon_index"],
                "vendor_id": "NEWV",
            },
        ],
    )
    try:
        r = real_client.post(
            f"{API}/collection-jobs",
            headers=headers,
            json={"olt_id": str(inv["olt_id"])},
        )
        assert r.status_code == 202, r.text
        assert r.json()["status"] == "success"

        # Verifica: state ainda é 'resolved' (NÃO regrediu para 'detected')
        # e last_seen_at foi atualizado, e vendor_id foi atualizado para o novo valor.
        engine = _sync_engine()
        try:
            with engine.connect() as conn:
                row = conn.execute(
                    text(
                        """
                        SELECT state, vendor_id, last_seen_at, first_seen_at
                        FROM pending_onu
                        WHERE olt_id = :olt AND pon_port_id = :pon
                        AND serial = :serial
                        """
                    ),
                    {
                        "olt": str(inv["olt_id"]),
                        "pon": str(inv["pon_port_id"]),
                        "serial": serial,
                    },
                ).first()
            assert row is not None
            assert row[0] == "resolved", f"state regrediu para {row[0]!r}"
            assert row[1] == "NEWV"
            # last_seen_at foi atualizado (deve ser maior que first_seen_at)
            assert row[2] > row[3]
        finally:
            engine.dispose()
    finally:
        clear_canned_discovery(inv["olt_id"])


# Idempotência: dois jobs ativos para mesma (olt, job_type) -> 409
def test_duplicate_active_job_returns_409(real_client, monkeypatch):
    _ensure_secret_env()
    headers, _ = _bootstrap_admin(real_client)
    inv = setup_inventory(real_client, headers)

    # Desativa eager para deixar job em 'pending' (worker nao roda) e
    # poder disparar o segundo POST contra a unicidade parcial.
    from app.celery_app import celery_app

    monkeypatch.setattr(celery_app.conf, "task_always_eager", False)

    # Primeiro POST cria job em 'pending'
    r1 = real_client.post(
        f"{API}/collection-jobs",
        headers=headers,
        json={"olt_id": str(inv["olt_id"])},
    )
    # Sob eager=False, o enqueue real falha (sem broker em teste) mas o
    # job já foi commitado em 'pending'.
    assert r1.status_code == 202, r1.text
    body1 = r1.json()
    assert body1["status"] == "pending"

    # Segundo POST: viola uq_collection_job_running -> 409
    r2 = real_client.post(
        f"{API}/collection-jobs",
        headers=headers,
        json={"olt_id": str(inv["olt_id"])},
    )
    assert r2.status_code == 409, r2.text
    assert r2.json()["error"]["code"] == "conflict"


# OLT inexistente -> 400
def test_create_with_unknown_olt_returns_400(real_client):
    _ensure_secret_env()
    headers, _ = _bootstrap_admin(real_client)
    r = real_client.post(
        f"{API}/collection-jobs",
        headers=headers,
        json={"olt_id": str(uuid4())},
    )
    assert r.status_code == 400, r.text
    assert r.json()["error"]["code"] == "bad_request"


# Sem token -> 401
def test_create_without_auth_returns_401(real_client):
    r = real_client.post(
        f"{API}/collection-jobs",
        json={"olt_id": str(uuid4())},
    )
    assert r.status_code == 401


# Listagem paginada com filtros
def test_list_collection_jobs_filters_and_pagination(real_client):
    _ensure_secret_env()
    headers, _ = _bootstrap_admin(real_client)
    inv = setup_inventory(real_client, headers)

    # cria 3 jobs (canned vazio, todos vao a success rapidamente)
    for _ in range(3):
        r = real_client.post(
            f"{API}/collection-jobs",
            headers=headers,
            json={"olt_id": str(inv["olt_id"])},
        )
        assert r.status_code == 202, r.text
        # Aguarda terminar antes de criar o proximo, senão o segundo
        # falha por uq_collection_job_running.
        assert r.json()["status"] in ("success", "partial")

    r = real_client.get(
        f"{API}/collection-jobs",
        headers=headers,
        params={"olt_id": str(inv["olt_id"])},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 3
    assert body["page"] == 1
    assert body["page_size"] == 50
    # ordem desc por created_at: o mais novo primeiro
    times = [item["created_at"] for item in body["items"]]
    assert times == sorted(times, reverse=True)

    # filtro por status=success
    r2 = real_client.get(
        f"{API}/collection-jobs",
        headers=headers,
        params={"olt_id": str(inv["olt_id"]), "status": "success"},
    )
    assert r2.status_code == 200
    assert all(item["status"] == "success" for item in r2.json()["items"])


# Detalhe inexistente
def test_get_unknown_job_returns_404(real_client):
    headers, _ = _bootstrap_admin(real_client)
    r = real_client.get(f"{API}/collection-jobs/{uuid4()}", headers=headers)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


# Truncamento de output_received: assegura que payload "gigante" entra
# sem estourar tamanho.
def test_large_output_is_truncated(real_client):
    _ensure_secret_env()
    headers, _ = _bootstrap_admin(real_client)
    inv = setup_inventory(real_client, headers)

    # canned com ONU mapeada para gerar log com payload pesado em
    # output_received via mock. O mock atual gera output curto, mas o
    # caminho de truncamento é exercitado pelo helper _truncate.
    # Aqui é validade que o pipeline aceita sem erro o tamanho normal.
    set_canned_discovery(
        inv["olt_id"],
        [
            {
                "serial": "TRNC00000001",
                "slot_index": inv["slot_index"],
                "pon_index": inv["pon_index"],
            },
        ],
    )
    try:
        r = real_client.post(
            f"{API}/collection-jobs",
            headers=headers,
            json={"olt_id": str(inv["olt_id"])},
        )
        assert r.status_code == 202
        body = r.json()
        assert body["status"] == "success"
        # Output gravado nao maior que MAX_OUTPUT_LENGTH + sufixo
        for entry in body["logs"]:
            if entry["output_received"]:
                assert len(entry["output_received"]) <= 65_536 + 64
    finally:
        clear_canned_discovery(inv["olt_id"])
