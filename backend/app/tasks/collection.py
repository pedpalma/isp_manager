# Tasks Celery do domínio collection.

# Três tasks:
# - run_discovery_job: cicla descoberta de ONUs não provisionadas.
# - run_signal_reading_job: cicla leitura de potência óptica.
# - detect_stale_jobs: P-M16 mitigation (D17.10). Marca como FAILED jobs
#   que ficaram em 'running' ou 'pending' além do threshold configurável.

# SEM autoretry. autoretry_for=() desativa qualquer retry implícito.
# Falha do job é terminal: error_message preservado, status=FAILED.
# Retry é novo POST manual pelo operador.

# As tasks de coleta delegam a lógica para os workers respectivos, que
# NUNCA propagam exception. As tasks em si só traduzem UUID e logam
# entrada/saída.

# IMPORTANTE: este arquivo é entregue COMPLETO para evitar erros de
# transcrição em SQL inline (a string AND virou ABD ao aplicar PATCH
# manual em revisão anterior).

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
    """Dispara o ciclo de descoberta de ONUs para um collection_job pendente.

    Import tardio do worker para evitar carregar modelos ORM no momento
    do registro da task (acontece no startup da API também)."""
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

    Mesmo contrato de run_discovery_job: import tardio, sem autoretry,
    jamais propaga exception. Falhas viram FAILED com error_message."""
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
    """Marca como FAILED jobs em 'running' ou 'pending' além do threshold.

    Mitigação interim de P-M16: enqueue Celery pode falhar após commit,
    deixando job em 'pending' eterno; worker pode crashar
    deixando 'running' eterno. detect_stale_jobs corre via Celery beat
    e termina esses jobs com error_message claro.

    Threshold lido de settings.optical.stale_job_threshold_minutes
    (default 10 min). Roda a cada 5 min via beat_schedule.

    Critério:
    - status='running' E started_at < cutoff
    - status='pending' E created_at < cutoff
    """
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
                    (status = CAST('running' AS job_status_enum) AND started_at < :cutoff)
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
