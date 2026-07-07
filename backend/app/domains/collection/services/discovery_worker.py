# Worker síncrono do ciclo de descoberta de ONUs.

# Executado dentro do worker Celery via app.tasks.collection.run_discovery_job.
# Usa sessão SÍNCRONA (psycopg) ao invés da async (asyncpg) da API. É fluxo
# distinto do CollectionJobService.create_discovery_job, que apenas cria
# o job no banco e enfileira a task.

# Fluxo em três fases, cada uma em sua transação:
# *Fase 1 (TX1): advisory lock por olt_id (impede colisão entre tipos
# diferentes de job na mesma OLT, R3/A4) -> carrega job + olt +
# credencial via _worker_common -> constrói OltConnectionConfig ->
# marca job como RUNNING. Lock de linha (FOR UPDATE) impede dois
# workers de pegarem o mesmo job.

# *Fase 2: chama adapter.list_unprovisioned_onus. O adapter é puro, não
# toca banco.

# *Fase 3 (TX2): grava todos os CommandLog em collection_log; resolve
# (slot_index, pon_index) -> pon_port_id via mapa em memoria;
# faz upsert em pending_onu sob a unicidade (olt_id, pon_port_id, serial);
# marca job como SUCCESS ou PARTIAL.

# Em caso de exception em qualquer fase:
# TX-erro separada marca job como FAILED com error_message.
# NUNCA propaga exception para o Celery.
# Sem autoretry (R3): falha do job é terminal, retry é novo POST manual.

# Truncamento de output_received (R8): valor > MAX_OUTPUT_LENGTH é
# cortado e marcado com sufixo de truncamento antes da gravação.

# Upsert NÃO toca state nem resolved_at: re-descoberta de
# uma ONU ja resolvida NUNCA regride para 'detected'.

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.adapters.olt.base import (
    CommandLog,
    DiscoveredOnu,
    OltConnectionConfig,
)
from app.adapters.olt.factory import get_olt_adapter
from app.db.session_sync import session_scope
from app.domains.collection.enums import JobStatus
from app.domains.collection.models.collection_job import CollectionJob
from app.domains.collection.models.collection_log import CollectionLog
from app.domains.collection.services._worker_common import (
    OltLockUnavailable,
    acquire_olt_advisory_lock,
    build_connection_config,
    load_olt_and_credential,
)

log = structlog.get_logger(__name__)

# Hard limit para output_received antes da gravação em collection_log.
# Saídas de comandos como "show unconfigured" em OLT grande chegam a
# centenas de KB. 64KB é suficiente para auditoria sem inchar a tabela.
MAX_OUTPUT_LENGTH = 65_536
_TRUNCATION_SUFFIX = "\n... [output truncated]"


class _DiscoveryAborted(Exception):
    """Marcador interno: o ciclo não deve continuar mas o job já foi
    devidamente marcado em outro lugar (job inexistente, já terminal,
    pego por outro worker)."""


def _truncate(value: str | None) -> str | None:
    if value is None:
        return None
    if len(value) <= MAX_OUTPUT_LENGTH:
        return value
    return value[:MAX_OUTPUT_LENGTH] + _TRUNCATION_SUFFIX


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)  # noqa: UP017


def run_discovery_job_sync(job_id: UUID) -> None:
    """Ponto de entrada chamado pelo Celery task.

    Nunca propaga exception ao chamador. Falhas viram job.status=FAILED
    com error_message preservado."""
    log.info("collection.worker.started", collection_job_id=str(job_id))

    # Fase 1: advisory lock + carrega tudo + resolve secret + marca RUNNING.
    try:
        connection_config, olt_id = _phase_load_and_mark_running(job_id)
    except _DiscoveryAborted:
        return
    except OltLockUnavailable as exc:
        log.warning(
            "collection.worker.lock_unavailable",
            collection_job_id=str(job_id),
            error=str(exc),
        )
        _mark_failed(job_id, f"phase1: {exc}")
        return
    except Exception as exc:
        log.exception(
            "collection.worker.phase1_failed",
            collection_job_id=str(job_id),
            error=str(exc),
        )
        _mark_failed(job_id, f"phase1: {exc}")
        return

    # Fase 2: chama adapter.
    try:
        adapter = get_olt_adapter()
        result = adapter.list_unprovisioned_onus(connection_config, olt_id=olt_id)
    except Exception as exc:
        log.exception(
            "collection.worker.phase2_failed",
            collection_job_id=str(job_id),
            olt_id=str(olt_id),
            error=str(exc),
        )
        _mark_failed(job_id, f"phase2: {exc}")
        return

    # Fase 3: persiste logs + upsert + marca status final (uma transação).
    try:
        unmapped_count = _phase_persist_results(
            job_id=job_id,
            olt_id=olt_id,
            command_logs=result.command_logs,
            discovered=result.discovered,
        )
    except Exception as exc:
        log.exception(
            "collection.worker.phase3_failed",
            collection_job_id=str(job_id),
            olt_id=str(olt_id),
            error=str(exc),
        )
        _mark_failed(job_id, f"phase3: {exc}")
        return

    final_status = JobStatus.PARTIAL if unmapped_count > 0 else JobStatus.SUCCESS
    _mark_finished(job_id, final_status, error_message=None)
    log.info(
        "collection.worker.finished",
        collection_job_id=str(job_id),
        olt_id=str(olt_id),
        status=final_status.value,
        discovered=len(result.discovered),
        unmapped=unmapped_count,
    )


def _phase_load_and_mark_running(job_id: UUID) -> tuple[OltConnectionConfig, UUID]:
    """Carrega job + olt + credencial, resolve segredo, marca RUNNING.

    Lock de linha (FOR UPDATE) impede dois workers de avançarem se a
    mesma task for entregue em duplicidade pelo broker. O segundo worker
    abortará em _DiscoveryAborted (status != PENDING).

    Advisory lock TRANSACIONAL por olt_id (R3/A4) impede colisão entre
    tipos diferentes de job (discovery vs signal_reading) na mesma OLT:
    equipamentos GPON aceitam poucas sessões SSH simultâneas, então
    serializa-se aqui antes mesmo de chegar no equipamento."""
    with session_scope() as db:
        job = _lock_pending_job(db, job_id)
        acquire_olt_advisory_lock(db, job.olt_id)
        olt, credential = load_olt_and_credential(db, job.olt_id)
        connection_config = build_connection_config(olt, credential)
        # Marca RUNNING. Commit pelo session_scope no fim do with.
        job.status = JobStatus.RUNNING
        job.started_at = _utcnow()
        return connection_config, job.olt_id


def _lock_pending_job(db: Session, job_id: UUID) -> CollectionJob:
    """SELECT ... FOR UPDATE da linha do job. Aborta se não estiver
    PENDING (job inexistente, já rodando, ou terminal)."""
    stmt = select(CollectionJob).where(CollectionJob.collection_job_id == job_id).with_for_update()
    job = db.execute(stmt).scalar_one_or_none()
    if job is None:
        log.error(
            "collection.worker.job_not_found",
            collection_job_id=str(job_id),
        )
        raise _DiscoveryAborted()
    if job.status != JobStatus.PENDING:
        log.warning(
            "collection.worker.job_not_pending",
            collection_job_id=str(job_id),
            current_status=str(job.status),
        )
        raise _DiscoveryAborted()
    return job


def _phase_persist_results(
    *,
    job_id: UUID,
    olt_id: UUID,
    command_logs: list[CommandLog],
    discovered: list[DiscoveredOnu],
) -> int:
    """Grava logs + upserts. Devolve número de ONUs descartadas por slot/pon
    não mapeado no inventário (alimenta decisão SUCCESS x PARTIAL)."""
    with session_scope() as db:
        _persist_command_logs(db, job_id=job_id, olt_id=olt_id, logs=command_logs)

        if not discovered:
            return 0

        pon_map = _load_pon_map(db, olt_id=olt_id)
        unmapped = 0
        for onu in discovered:
            key = (onu.slot_index, onu.pon_index)
            pon_port_id = pon_map.get(key)
            if pon_port_id is None:
                unmapped += 1
                log.warning(
                    "collection.worker.unmapped_onu",
                    collection_job_id=str(job_id),
                    olt_id=str(olt_id),
                    serial=onu.serial,
                    slot_index=onu.slot_index,
                    pon_index=onu.pon_index,
                )
                continue
            _upsert_pending_onu(
                db,
                olt_id=olt_id,
                pon_port_id=pon_port_id,
                serial=onu.serial,
                vendor_id=onu.vendor_id,
                pon_position=onu.pon_position,
                raw_payload=onu.raw_payload,
                discovery_source=f"job:{job_id}",
            )
        return unmapped


def _persist_command_logs(
    db: Session,
    *,
    job_id: UUID,
    olt_id: UUID,
    logs: list[CommandLog],
) -> None:
    for entry in logs:
        db.add(
            CollectionLog(
                collection_job_id=job_id,
                olt_id=olt_id,
                step_name=entry.step_name,
                command_sent=entry.command_sent,
                output_received=_truncate(entry.output_received),
                parser_status=entry.parser_status,
                success=entry.success,
                duration_ms=entry.duration_ms,
            )
        )
    db.flush()


def _load_pon_map(db: Session, *, olt_id: UUID) -> dict[tuple[int, int], UUID]:
    """Mapa (slot_index, pon_index) -> pon_port_id para esta OLT.

    Uma única query agregada em Python. Carregada por job, não por ONU."""
    stmt = text(
        """
        SELECT s.slot_index, pp.pon_index, pp.pon_port_id
        FROM pon_port pp
        JOIN slot s ON s.slot_id = pp.slot_id
        JOIN chassis c ON c.chassis_id = s.chassis_id
        WHERE c.olt_id = :olt_id
        """
    )
    rows = db.execute(stmt, {"olt_id": str(olt_id)}).all()
    out: dict[tuple[int, int], UUID] = {}
    for slot_idx, pon_idx, pon_port_id in rows:
        out[(int(slot_idx), int(pon_idx))] = pon_port_id
    return out


def _upsert_pending_onu(
    db: Session,
    *,
    olt_id: UUID,
    pon_port_id: UUID,
    serial: str,
    vendor_id: str | None,
    pon_position: int | None,
    raw_payload: dict[str, Any] | None,
    discovery_source: str,
) -> None:
    """INSERT ... ON CONFLICT (olt_id, pon_port_id, serial) DO UPDATE.

    DELIBERADAMENTE NÃO toca state, resolved_at, linked_onu_id,
    resolution_type, first_seen_at. Re-descoberta nunca regride o ciclo
    de resolução."""
    import json

    normalized_serial = serial.strip().upper()

    stmt = text(
        """
        INSERT INTO pending_onu (
            olt_id, pon_port_id, serial, vendor_id, pon_position,
            raw_payload, discovery_source,
            first_seen_at, last_seen_at
        ) VALUES (
            :olt_id, :pon_port_id, :serial, :vendor_id, :pon_position,
            CAST(:raw_payload AS JSONB), :discovery_source,
            NOW(), NOW()
        )
        ON CONFLICT (olt_id, pon_port_id, serial) DO UPDATE SET
            vendor_id = EXCLUDED.vendor_id,
            pon_position = EXCLUDED.pon_position,
            raw_payload = EXCLUDED.raw_payload,
            discovery_source = EXCLUDED.discovery_source,
            last_seen_at = NOW()
        """
    )
    db.execute(
        stmt,
        {
            "olt_id": str(olt_id),
            "pon_port_id": str(pon_port_id),
            "serial": normalized_serial,
            "vendor_id": vendor_id,
            "pon_position": pon_position,
            "raw_payload": json.dumps(raw_payload) if raw_payload is not None else None,
            "discovery_source": discovery_source,
        },
    )


def _mark_failed(job_id: UUID, error_message: str) -> None:
    """Tenta marcar o job como FAILED em uma transação curta a parte.

    Best-effort: se a própria escrita falhar é feito o log. Worker não deve travar."""
    try:
        with session_scope() as db:
            db.execute(
                text(
                    """
                    UPDATE collection_job
                    SET status = CAST('failed' AS job_status_enum),
                        finished_at = NOW(),
                        error_message = :err
                    WHERE collection_job_id = :j
                    """
                ),
                {"err": error_message[:1000], "j": str(job_id)},
            )
    except Exception as exc:
        log.exception(
            "collection.worker.mark_failed_failed",
            collection_job_id=str(job_id),
            error=str(exc),
        )


def _mark_finished(job_id: UUID, status: JobStatus, *, error_message: str | None) -> None:
    """Marca o job em status terminal (success/partial)."""
    with session_scope() as db:
        db.execute(
            text(
                """
                UPDATE collection_job
                    SET status = CAST(:status AS job_status_enum),
                        finished_at = NOW(),
                        error_message = :err
                WHERE collection_job_id = :j
                """
            ),
            {
                "status": status.value,
                "err": error_message,
                "j": str(job_id),
            },
        )
