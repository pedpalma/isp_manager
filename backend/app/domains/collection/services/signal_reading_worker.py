# Worker síncrono do ciclo de leitura óptica.
# Espelha discovery_worker: 3 fases isoladas, falha terminal, sem retry.

# Fase 1 (TX1): advisory lock por olt_id -> carrega olt + credencial ->
#   constrói config -> marca RUNNING. SELECT FOR UPDATE no job protege
#   contra entrega duplicada pelo broker.
# Fase 2: chama adapter.list_optical_readings. Adapter e puro, não toca banco.
# Fase 3 (TX2): grava optical_reading por ONU + atualiza last_signal_at
#   e last_collected_at em onu_runtime_state + resolve thresholds (cache
#   TTL) + cria/atualiza optical_alert_event + grava collection_log.
#   Marca SUCCESS ou PARTIAL (PARTIAL se houve leitura com serial sem
#   ONU viva correspondente, R7).
# UNKNOWN serial: descarte com log WARN, conta para PARTIAL.
# Alertas: upsert logico via uq_optical_alert_open. Se já existe open
#   para o par (onu, metric), so atualiza value (NAO regride
#   triggered_at). Quando volta ao range, V1 NAO auto-resolve.

# Sem autoretry: igual discovery. Falha de qualquer fase vira FAILED em
# TX separada via _mark_failed (reusada do discovery_worker).

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from app.adapters.olt.base import OltConnectionConfig
from app.adapters.olt.factory import get_olt_adapter
from app.core.config import settings
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
from app.domains.optical.enums import SUPPORTED_OPTICAL_METRICS, OpticalScopeType
from app.domains.optical.models.optical_threshold_policy import (
    OpticalThresholdPolicy,
)
from app.domains.optical.services.threshold_cache import (
    ThresholdCache,
    is_miss,
    resolve_policies_for_onu,
)

log = structlog.get_logger(__name__)

MAX_OUTPUT_LENGTH = 65_536
_TRUNCATION_SUFFIX = "\n... [output truncated]"


class _SignalReadingAborted(Exception):
    """Marcador interno; job já foi marcado adequadamente em outro lugar."""


def _truncate(value: str | None) -> str | None:
    if value is None:
        return None
    if len(value) <= MAX_OUTPUT_LENGTH:
        return value
    return value[:MAX_OUTPUT_LENGTH] + _TRUNCATION_SUFFIX


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)  # noqa: UP017


def run_signal_reading_job_sync(job_id: UUID) -> None:
    """Ponto de entrada chamado pelo Celery task.

    Não propaga exception. Falhas viram job.status=FAILED com error_message."""
    log.info("collection.worker.signal_reading.started", collection_job_id=str(job_id))

    # Fase 1
    try:
        connection_config, olt_id = _phase_load_and_mark_running(job_id)
    except _SignalReadingAborted:
        return
    except OltLockUnavailable as exc:
        log.warning(
            "collection.worker.signal_reading.lock_unavailable",
            collection_job_id=str(job_id),
            error=str(exc),
        )
        _mark_failed(job_id, f"phase1: {exc}")
        return
    except Exception as exc:
        log.exception(
            "collection.worker.signal_reading.phase1_failed",
            collection_job_id=str(job_id),
            error=str(exc),
        )
        _mark_failed(job_id, f"phase1: {exc}")
        return

    # Fase 2
    try:
        adapter = get_olt_adapter()
        result = adapter.list_optical_readings(connection_config, olt_id=olt_id)
    except Exception as exc:
        log.exception(
            "collection.worker.signal_reading.phase2_failed",
            collection_job_id=str(job_id),
            olt_id=str(olt_id),
            error=str(exc),
        )
        _mark_failed(job_id, f"phase2: {exc}")
        return

    # Fase 3
    try:
        unknown_count, persisted_count, alert_count = _phase_persist_readings(
            job_id=job_id,
            olt_id=olt_id,
            command_logs=result.command_logs,
            readings=result.readings,
        )
    except Exception as exc:
        log.exception(
            "collection.worker.signal_reading.phase3_failed",
            collection_job_id=str(job_id),
            olt_id=str(olt_id),
            error=str(exc),
        )
        _mark_failed(job_id, f"phase3: {exc}")
        return

    final_status = JobStatus.PARTIAL if unknown_count > 0 else JobStatus.SUCCESS
    _mark_finished(job_id, final_status)
    log.info(
        "collection.worker.signal_reading.finished",
        collection_job_id=str(job_id),
        olt_id=str(olt_id),
        status=final_status.value,
        readings_total=len(result.readings),
        persisted=persisted_count,
        unknown_serial=unknown_count,
        alerts_touched=alert_count,
    )


def _phase_load_and_mark_running(job_id: UUID) -> tuple[OltConnectionConfig, UUID]:
    """Lock + load + RUNNING em uma transação."""
    with session_scope() as db:
        job = _lock_pending_job(db, job_id)
        # Advisory lock por olt_id contra concorrência inter-jobs (A4/R3).
        acquire_olt_advisory_lock(db, job.olt_id)

        olt, credential = load_olt_and_credential(db, job.olt_id)
        connection_config = build_connection_config(olt, credential)

        job.status = JobStatus.RUNNING
        job.started_at = _utcnow()
        return connection_config, job.olt_id


def _lock_pending_job(db: Session, job_id: UUID) -> CollectionJob:
    stmt = select(CollectionJob).where(CollectionJob.collection_job_id == job_id).with_for_update()
    job = db.execute(stmt).scalar_one_or_none()
    if job is None:
        log.error(
            "collection.worker.signal_reading.job_not_found",
            collection_job_id=str(job_id),
        )
        raise _SignalReadingAborted()
    if job.status != JobStatus.PENDING:
        log.warning(
            "collection.worker.signal_reading.job_not_pending",
            collection_job_id=str(job_id),
            current_status=str(job.status),
        )
        raise _SignalReadingAborted()
    return job


def _phase_persist_readings(
    *,
    job_id: UUID,
    olt_id: UUID,
    command_logs: list[Any],
    readings: list[Any],
) -> tuple[int, int, int]:
    """Persiste tudo + decide SUCCESS x PARTIAL.

    Devolve (unknown_count, persisted_count, alert_count):
    - unknown_count: serials sem ONU viva mapeada (vira PARTIAL).
    - persisted_count: leituras gravadas em optical_reading.
    - alert_count: alertas criados ou tocados (debug)."""
    cache = ThresholdCache(ttl_seconds=settings.optical.threshold_cache_ttl_seconds)

    with session_scope() as db:
        _persist_command_logs(db, job_id=job_id, olt_id=olt_id, logs=command_logs)

        if not readings:
            return 0, 0, 0

        # Resolve serial -> (onu_id, pon_port_id, olt_id_chain) em lote.
        serial_map = _load_serial_map(db, olt_id=olt_id)

        unknown = 0
        persisted = 0
        alert_count = 0
        for reading in readings:
            entry = serial_map.get(reading.serial)
            if entry is None:
                unknown += 1
                log.warning(
                    "collection.worker.signal_reading.unknown_serial",
                    collection_job_id=str(job_id),
                    olt_id=str(olt_id),
                    serial=reading.serial,
                )
                continue
            onu_id, pon_port_id = entry

            # Resolve thresholds via cache.
            thresholds = _resolve_thresholds_with_cache(
                db, cache=cache, onu_id=onu_id, pon_port_id=pon_port_id, olt_id=olt_id
            )

            # Detecta violações para flag alert_critical.
            alert_critical = _has_critical_violation(reading, thresholds)

            # Insere reading. PK composta + partição por collected_at
            # cuidam do roteamento da linha.
            _insert_optical_reading(
                db,
                onu_id=onu_id,
                reading=reading,
                alert_critical=alert_critical,
                collection_source=f"job:{job_id}",
            )
            persisted += 1

            # Atualiza onu_runtime_state.last_signal_at e last_collected_at.
            _touch_runtime_state(db, onu_id=onu_id, when=reading.collected_at)

            # Avalia thresholds métrica por métrica; upsert logico de alertas.
            metric_values = _reading_metric_values(reading)
            for metric, value in metric_values.items():
                if value is None:
                    continue
                policy = thresholds.get(metric)
                if policy is None:
                    continue
                violated = _check_violation(value, policy.threshold_min, policy.threshold_max)
                if violated:
                    _upsert_open_alert(
                        db,
                        onu_id=onu_id,
                        policy_id=policy.optical_threshold_policy_id,
                        metric_name=metric,
                        value=value,
                    )
                    alert_count += 1

        return unknown, persisted, alert_count


def _persist_command_logs(
    db: Session,
    *,
    job_id: UUID,
    olt_id: UUID,
    logs: list[Any],
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


def _load_serial_map(db: Session, *, olt_id: UUID) -> dict[str, tuple[UUID, UUID]]:
    """Mapa serial -> (onu_id, pon_port_id) para ONUs vivas naquela OLT.
    Uma query agregada. Serials não mapeados serão descartados em fase 3."""
    stmt = text(
        """
        SELECT o.serial, o.onu_id, o.pon_port_id
        FROM onu o
        JOIN pon_port pp ON pp.pon_port_id = o.pon_port_id
        JOIN slot s ON s.slot_id = pp.slot_id
        JOIN chassis c ON c.chassis_id = s.chassis_id
        WHERE c.olt_id = :olt_id
        AND o.deleted_at IS NULL
        """
    )
    rows = db.execute(stmt, {"olt_id": str(olt_id)}).all()
    return {serial: (onu_id, pon_port_id) for serial, onu_id, pon_port_id in rows}


def _resolve_thresholds_with_cache(
    db: Session,
    *,
    cache: ThresholdCache,
    onu_id: UUID,
    pon_port_id: UUID,
    olt_id: UUID,
):
    """Devolve dict metric_name -> EffectiveThreshold|None usando cache."""
    # Usa cache se todas as metrics estiverem presentes.
    cached: dict[str, Any] = {}
    needs_reload = False
    for metric in SUPPORTED_OPTICAL_METRICS:
        value = cache.get(onu_id, metric)
        if is_miss(value):
            needs_reload = True
            break
        cached[metric] = value
    if not needs_reload:
        return cached

    # Cache miss: carrega politicas e resolve.
    stmt = (
        select(OpticalThresholdPolicy)
        .where(OpticalThresholdPolicy.active.is_(True))
        .where(
            or_(
                (OpticalThresholdPolicy.scope_type == OpticalScopeType.ONU)
                & (OpticalThresholdPolicy.scope_id == onu_id),
                (OpticalThresholdPolicy.scope_type == OpticalScopeType.PON_PORT)
                & (OpticalThresholdPolicy.scope_id == pon_port_id),
                (OpticalThresholdPolicy.scope_type == OpticalScopeType.OLT)
                & (OpticalThresholdPolicy.scope_id == olt_id),
                OpticalThresholdPolicy.scope_type == OpticalScopeType.GLOBAL,
            )
        )
    )
    policies = db.execute(stmt).scalars().all()
    resolved = resolve_policies_for_onu(policies)
    cache.put_bulk(onu_id, resolved)
    return resolved


def _reading_metric_values(reading: Any) -> dict[str, float | None]:
    """Extrai cada métrica suportada do DTO."""
    return {
        "rx_power_dbm": reading.rx_power_dbm,
        "tx_power_dbm": reading.tx_power_dbm,
        "temperature": reading.temperature,
        "voltage": reading.voltage,
        "bias_current": reading.bias_current,
        "distance_m": reading.distance_m,
    }


def _check_violation(
    value: float,
    threshold_min: float | None,
    threshold_max: float | None,
) -> bool:
    if threshold_min is not None and value < threshold_min:
        return True
    if threshold_max is not None and value > threshold_max:  # noqa: SIM103
        return True
    return False


def _has_critical_violation(reading: Any, thresholds: dict[str, Any]) -> bool:
    """Conveniência: marca optical_reading.alert_critical=true quando
    pelo menos UMA métrica violou um threshold de severidade 'critical'.

    Flag operacional para listagem rápida; não substitui optical_alert_event."""
    values = _reading_metric_values(reading)
    for metric, value in values.items():
        if value is None:
            continue
        policy = thresholds.get(metric)
        if policy is None:
            continue
        if policy.severity.value != "critical":
            continue
        if _check_violation(value, policy.threshold_min, policy.threshold_max):
            return True
    return False


def _insert_optical_reading(
    db: Session,
    *,
    onu_id: UUID,
    reading: Any,
    alert_critical: bool,
    collection_source: str,
) -> None:
    stmt = text(
        """
        INSERT INTO optical_reading (
            onu_id, rx_power_dbm, tx_power_dbm, status,
            alert_critical, distance_m, temperature, voltage,
            bias_current, collected_at, collection_source
        ) VALUES (
            :onu_id, :rx, :tx, :status,
            :alert_critical, :distance_m, :temperature, :voltage,
            :bias_current, :collected_at, :collection_source
        )
        """
    )
    db.execute(
        stmt,
        {
            "onu_id": str(onu_id),
            "rx": reading.rx_power_dbm,
            "tx": reading.tx_power_dbm,
            "status": reading.status,
            "alert_critical": alert_critical,
            "distance_m": reading.distance_m,
            "temperature": reading.temperature,
            "voltage": reading.voltage,
            "bias_current": reading.bias_current,
            "collected_at": reading.collected_at,
            "collection_source": collection_source,
        },
    )


def _touch_runtime_state(db: Session, *, onu_id: UUID, when: datetime) -> None:
    """Atualiza last_signal_at e last_collected_at. A linha sempre existe.
    NÃO altera connection_status: presença de leitura não implica 'online'."""
    db.execute(
        text(
            """
            UPDATE onu_runtime_state
            SET last_signal_at = :when,
                last_collected_at = :when,
                updated_at = NOW()
            WHERE onu_id = :onu_id
            """
        ),
        {"onu_id": str(onu_id), "when": when},
    )


def _upsert_open_alert(
    db: Session,
    *,
    onu_id: UUID,
    policy_id: UUID,
    metric_name: str,
    value: float,
) -> None:
    """Upsert logico contra uq_optical_alert_open (migration 0004).
    Se já existe alerta 'open' para (onu_id, metric_name), sá atualiza
    value (mantém triggered_at original). Não auto-resolve quando volta ao range."""

    # ON CONFLICT em partial index e suportado pelo Postgres usando o nome do index em WHERE.
    stmt = text(
        """
        INSERT INTO optical_alert_event (
            onu_id, policy_id, metric_name, value, status, triggered_at
        ) VALUES (
            :onu_id, :policy_id, :metric_name, :value, 'open', NOW()
        )
        ON CONFLICT (onu_id, metric_name) WHERE status = 'open'
        DO UPDATE SET
            value = EXCLUDED.value
        """
    )
    db.execute(
        stmt,
        {
            "onu_id": str(onu_id),
            "policy_id": str(policy_id),
            "metric_name": metric_name,
            "value": value,
        },
    )


def _mark_failed(job_id: UUID, error_message: str) -> None:
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
            "collection.worker.signal_reading.mark_failed_failed",
            collection_job_id=str(job_id),
            error=str(exc),
        )


def _mark_finished(job_id: UUID, status: JobStatus) -> None:
    with session_scope() as db:
        db.execute(
            text(
                """
                UPDATE collection_job
                SET status = CAST(:status AS job_status_enum),
                    finished_at = NOW(),
                    error_message = NULL
                WHERE collection_job_id = :j
                """
            ),
            {"status": status.value, "j": str(job_id)},
        )
