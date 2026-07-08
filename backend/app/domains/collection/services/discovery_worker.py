# Worker síncrono do ciclo de descoberta de ONUs.

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
        connection_config, olt_id, manufacturer_id, manufacturer_slug = (
            _phase_load_and_mark_running(job_id)
        )
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

    # Fase 2: chama adapter. Factory decide pelo manufacturer_slug da OLT.
    try:
        adapter = get_olt_adapter(manufacturer_slug=manufacturer_slug)
        result = adapter.list_unprovisioned_onus(connection_config, olt_id=olt_id)
    except Exception as exc:
        log.exception(
            "collection.worker.phase2_failed",
            collection_job_id=str(job_id),
            olt_id=str(olt_id),
            manufacturer_slug=manufacturer_slug,
            error=str(exc),
        )
        _mark_failed(job_id, f"phase2: {exc}")
        return

    # Fase 3: persiste logs + upsert + marca status final (uma transação).
    try:
        unmapped_count = _phase_persist_results(
            job_id=job_id,
            olt_id=olt_id,
            manufacturer_id=manufacturer_id,
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


def _phase_load_and_mark_running(
    job_id: UUID,
) -> tuple[OltConnectionConfig, UUID, UUID, str | None]:
    """Carrega job + olt + credencial, resolve segredo, marca RUNNING."""
    with session_scope() as db:
        job = _lock_pending_job(db, job_id)
        acquire_olt_advisory_lock(db, job.olt_id)
        olt, credential = load_olt_and_credential(db, job.olt_id)
        connection_config = build_connection_config(olt, credential)

        # Resolve manufacturer_id + slug da OLT em uma única query.
        # A OLT sempre tem olt_model (FK NOT NULL) e olt_model sempre
        # tem manufacturer (FK NOT NULL), então row nunca é None aqui;
        # se for, é corrupção do inventário e cai como Exception genérica.
        mfr_row = db.execute(
            text(
                """
                SELECT m.manufacturer_id, m.slug
                FROM olt o
                JOIN olt_model om ON om.olt_model_id = o.olt_model_id
                JOIN manufacturer m ON m.manufacturer_id = om.manufacturer_id
                WHERE o.olt_id = :olt_id
                """
            ),
            {"olt_id": str(job.olt_id)},
        ).first()
        if mfr_row is None:
            raise RuntimeError(
                f"Inventário inconsistente: olt {job.olt_id} sem manufacturer via olt_model."
            )
        manufacturer_id = UUID(str(mfr_row[0]))
        manufacturer_slug = mfr_row[1]

        # Marca RUNNING. Commit pelo session_scope no fim do with.
        job.status = JobStatus.RUNNING
        job.started_at = _utcnow()
        return connection_config, job.olt_id, manufacturer_id, manufacturer_slug


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
    manufacturer_id: UUID,
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
        onu_model_map = _load_onu_model_map(db, manufacturer_id=manufacturer_id)
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

            # Matching por vendor_id. Sem vendor_id (adapter falhou em
            # ler, ou vendor não expõe): resolved fica None e o UPDATE
            # preserva match anterior via COALESCE.
            resolved_onu_model_id: UUID | None = None
            if onu.vendor_id is not None:
                lookup_key = onu.vendor_id.strip().upper()
                resolved_onu_model_id = onu_model_map.get(lookup_key)
                if resolved_onu_model_id is None:
                    log.info(
                        "collection.worker.vendor_id_unmatched",
                        collection_job_id=str(job_id),
                        olt_id=str(olt_id),
                        vendor_id=lookup_key,
                    )

            _upsert_pending_onu(
                db,
                olt_id=olt_id,
                pon_port_id=pon_port_id,
                serial=onu.serial,
                vendor_id=onu.vendor_id,
                pon_position=onu.pon_position,
                raw_payload=onu.raw_payload,
                discovery_source=f"job:{job_id}",
                onu_model_id=resolved_onu_model_id,
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


def _load_onu_model_map(db: Session, *, manufacturer_id: UUID) -> dict[str, UUID]:
    """Mapa vendor_id (uppercase) -> onu_model_id para os modelos ativos
    do manufacturer da OLT."""
    stmt = text(
        """
        SELECT vendor_id, onu_model_id
        FROM onu_model
        WHERE manufacturer_id = :mfr
        AND vendor_id IS NOT NULL
        AND active = TRUE
        """
    )
    rows = db.execute(stmt, {"mfr": str(manufacturer_id)}).all()
    out: dict[str, UUID] = {}
    for vendor_id, onu_model_id in rows:
        normalized = vendor_id.strip().upper()
        if normalized in out and out[normalized] != onu_model_id:
            # Caso patológico: dois onu_model com o mesmo vendor_id
            # normalizado. Não deveria ocorrer na prática (cadastro
            # convenciona uppercase). Last-write-wins + log.
            log.warning(
                "collection.worker.vendor_id_ambiguous",
                manufacturer_id=str(manufacturer_id),
                vendor_id=normalized,
            )
        out[normalized] = UUID(str(onu_model_id))
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
    onu_model_id: UUID | None,
) -> None:
    """INSERT ... ON CONFLICT (olt_id, pon_port_id, serial) DO UPDATE."""
    import json

    normalized_serial = serial.strip().upper()

    stmt = text(
        """
        INSERT INTO pending_onu (
            olt_id, pon_port_id, serial, vendor_id, pon_position,
            raw_payload, discovery_source, onu_model_id,
            first_seen_at, last_seen_at
        ) VALUES (
            :olt_id, :pon_port_id, :serial, :vendor_id, :pon_position,
            CAST(:raw_payload AS JSONB), :discovery_source, :onu_model_id,
            NOW(), NOW()
        )
        ON CONFLICT (olt_id, pon_port_id, serial) DO UPDATE SET
            vendor_id = EXCLUDED.vendor_id,
            pon_position = EXCLUDED.pon_position,
            raw_payload = EXCLUDED.raw_payload,
            discovery_source = EXCLUDED.discovery_source,
            onu_model_id = COALESCE(EXCLUDED.onu_model_id, pending_onu.onu_model_id),
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
            "onu_model_id": str(onu_model_id) if onu_model_id is not None else None,
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
