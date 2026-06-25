# Tasks Celery do domínio collection.

# SEM autoretry. autoretry_for=() desativa qualquer retry implícito.
# Falha do job é terminal: error_message preservado, status=FAILED.
# Retry é novo POST manual pelo operador.

# A task delega a lógica para discovery_worker.run_discovery_job_sync,
# que NUNCA propaga exception. A task em si só traduz UUID e loga entrada/Saida.

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import structlog
from sqlalchemy import text

from app.celery_app import celery_app
from app.core.config import settings
from app.db.session_sync import session_scope

log = structlog.get_logger(__name__)


@celery_app.task(name="app.tasks.collection.run_discovery_job", autoretry_for=())
def run_discovery_job(collection_job_id: str) -> str:
    # Import tardio: discovery_worker importa modelos ORM, que importam
    # a engine; isso sé é necessário no contexto do worker, não no registro da task.
    from app.domains.collection.services.discovery_worker import (
        run_discovery_job_sync,
    )

    job_id = UUID(collection_job_id)
    log.info("collection.task.received", collection_job_id=str(job_id))
    run_discovery_job_sync(job_id)
    log.info("collection.task.completed", collection_job_id=str(job_id))
    return str(job_id)


@celery_app.task(name="app.tasks.collection.run_signal_reading_job", autoretry_for=())
def run_signal_reading_job(collection_job_id: str) -> str:
    """Dispara o ciclo de leitura óptica para um collection_job pendente.
    Falhas viram FAILED com error_message preservado."""
    from app.domains.collection.services.signal_reading_worker import (
        run_signal_reading_job_sync,
    )

    job_id = UUID(collection_job_id)
    log.info(
        "collection.task.signal_reading.received",
        collection_job_id=str(job_id),
    )
    run_signal_reading_job_sync(job_id)
    log.info(
        "collection.task.signal_reading.completed",
        collection_job_id=str(job_id),
    )
    return str(job_id)


@celery_app.task(name="app.tasks.collection.detect_stale_jobs", autoretry_for=())
def detect_stale_jobs() -> dict[str, list[str]]:
    """Marca jobs em 'running' além do threshold como 'failed'."""
    threshold_minutes = settings.optical.stale_job_threshold_minutes
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=threshold_minutes)  # noqa: UP017
    stale_ids: list[str] = []
    with session_scope() as db:
        rows = db.execute(
            text(
                """
                SELECT collection_job_id
                FROM collection_job
                WHERE (
                    (status = CAST('running' AS job_status_enum) ABD started_at < :cutoff)
                    OR (status = CAST('pending' AS job_status_enum) AND created_at < :cutoff)
                )
                """
            ),
            {"cutoff": cutoff},
        ).all()
        for (job_id,) in rows:
            stale_ids.append(str(job_id))
            db.execute(
                text(
                    """
                    UPDATE collection_job
                    SET status = CAST('failed' AS job_status_enum),
                        finished_at = NOW(),
                        error_message = 'detected as stale by detect_stale_jobs'
                    WHERE collection_job_id = :id
                    """
                ),
                {"id": job_id},
            )
    if stale_ids:
        log.warning(
            "collection.stale_jobs_detected",
            count=len(stale_ids),
            stale_jobs=stale_ids,
        )
    return {"stale_jobs": stale_ids}
