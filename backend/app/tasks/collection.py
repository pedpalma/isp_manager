# Tasks Celery do domínio collection.

# SEM autoretry. autoretry_for=() desativa qualquer retry implícito.
# Falha do job é terminal: error_message preservado, status=FAILED.
# Retry é novo POST manual pelo operador.

# A task delega a lógica para discovery_worker.run_discovery_job_sync,
# que NUNCA propaga exception. A task em si só traduz UUID e loga entrada/Saida.

from __future__ import annotations

from uuid import UUID

import structlog

from app.celery_app import celery_app

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
