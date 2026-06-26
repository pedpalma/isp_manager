# Rotas /api/v1/collection-jobs.

# POST é síncrono no que toca ao banco (commita o job),
# enfileira a task ASSÍNCRONA, devolve 202.
# Todas as rotas exigem JWT + require_admin.

# Sem DELETE: jobs são append-only (history).

# Sob task_always_eager=True (testes), o .delay() roda síncrono no
# mesmo processo e atualiza o DB para o status terminal antes de
# retornar. O objeto job em memória, porém, foi obtido ANTES do delay
# pela sessão async da rota: continua com status='pending'. Para refletir
# o estado terminal na resposta (e para que os testes possam afirmar
# sobre status pós-eager), refazemos um get_detail() APÓS o delay.
# Em produção (não-eager) o get_detail também roda mas devolve 'pending',
# o que é o estado correto naquele momento.

# Janela de órfão: commit do job + enqueue Celery não são atômicos.
# Se o enqueue falhar após o commit, o job fica 'pending' para sempre;
# detect_stale_jobs (beat) marca como failed após threshold.

from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_actor, require_admin
from app.core.actor import Actor
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_session
from app.domains.collection.enums import JobStatus
from app.domains.collection.schemas.collection_job import (
    CollectionJobCreate,
    CollectionJobDetailRead,
    CollectionJobRead,
)
from app.domains.collection.services.collection_job import CollectionJobService
from app.tasks.collection import run_discovery_job, run_signal_reading_job

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/collection-jobs", tags=["collection:jobs"])


def get_service(session: AsyncSession = Depends(get_session)) -> CollectionJobService:
    return CollectionJobService(session)


@router.get(
    "",
    response_model=Page[CollectionJobRead],
    dependencies=[Depends(require_admin)],
)
async def list_collection_jobs(
    olt_id: UUID | None = Query(default=None),
    status_filter: JobStatus | None = Query(default=None, alias="status"),
    params: PageParams = Depends(page_params),
    service: CollectionJobService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> Page[CollectionJobRead]:
    return await service.list_page(
        params=params,
        olt_id=olt_id,
        status_filter=status_filter,
        actor=actor,
    )


@router.get(
    "/{collection_job_id}",
    response_model=CollectionJobDetailRead,
    dependencies=[Depends(require_admin)],
)
async def get_collection_job(
    collection_job_id: UUID,
    service: CollectionJobService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> CollectionJobDetailRead:
    return await service.get_detail(collection_job_id, actor=actor)


@router.post(
    "",
    response_model=CollectionJobDetailRead,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_admin)],
)
async def create_discovery_job(
    payload: CollectionJobCreate,
    service: CollectionJobService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> CollectionJobDetailRead:
    """Dispara descoberta de ONUs não provisionadas para uma OLT.

    Cria job em 'pending', commita, enfileira a task Celery, refecha o
    detalhe atualizado e retorna. Sob testes com task_always_eager=True
    o detalhe já reflete status terminal (success/partial/failed)."""
    job = await service.create_discovery_job(
        olt_id=payload.olt_id,
        actor=actor,
    )
    try:
        run_discovery_job.delay(str(job.collection_job_id))
    except Exception as exc:
        log.error(
            "collection.enqueue_failed",
            collection_job_id=str(job.collection_job_id),
            job_type="discovery",
            error=str(exc),
        )
    # Refetch após delay para refletir status pós-worker (sob eager) ou
    # pós-commit (em produção). Mesmo método usado em GET detail.
    return await service.get_detail(job.collection_job_id, actor=actor)


@router.post(
    "/signal-reading",
    response_model=CollectionJobDetailRead,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_admin)],
)
async def create_signal_reading_job(
    payload: CollectionJobCreate,
    service: CollectionJobService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> CollectionJobDetailRead:
    """Dispara coleta de potência óptica para uma OLT.

    Mesmo padrão da rota de discovery: cria + enqueue + refetch.
    Idempotência concorrente por uq_collection_job_running (compartilhada
    entre discovery e signal_reading)."""
    job = await service.create_signal_reading_job(
        olt_id=payload.olt_id,
        actor=actor,
    )
    try:
        run_signal_reading_job.delay(str(job.collection_job_id))
    except Exception as exc:
        log.error(
            "collection.enqueue_failed",
            collection_job_id=str(job.collection_job_id),
            job_type="signal_reading",
            error=str(exc),
        )
    return await service.get_detail(job.collection_job_id, actor=actor)
