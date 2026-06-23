# Rotas /api/v1/collection-jobs.

# POST é síncrono no que toca ao banco (commita o job),
# enfileira a task ASSÍNCRONA, devolve 202.
# Todas as rotas exigem JWT + require_admin.

# Sem DELETE: jobs são append-only (history).

# Janela de órfão: commit do job + enqueue Celery não são atômicos.
# Se o enqueue falhar após o commit, o job fica 'pending' para sempre.
# TODO: fix real.

from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, require_admin
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_session
from app.domains.collection.enums import JobStatus
from app.domains.collection.schemas.collection_job import (
    CollectionJobCreate,
    CollectionJobDetailRead,
    CollectionJobRead,
)
from app.domains.collection.services.collection_job import CollectionJobService

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/collection-jobs", tags=["collection:jobs"])


def get_collection_job_service(
    session: AsyncSession = Depends(get_session),
) -> CollectionJobService:
    return CollectionJobService(session)


@router.get("", response_model=Page[CollectionJobRead])
async def list_collection_jobs(
    olt_id: UUID | None = Query(default=None),
    status_filter: JobStatus | None = Query(default=None, alias="status"),
    params: PageParams = Depends(page_params),
    current: CurrentUser = Depends(require_admin),
    service: CollectionJobService = Depends(get_collection_job_service),
) -> Page[CollectionJobRead]:
    return await service.list_page(
        params=params,
        olt_id=olt_id,
        status_filter=status_filter,
        actor=current.to_actor(),
    )


@router.get("/{collection_job_id}", response_model=CollectionJobDetailRead)
async def get_collection_job(
    collection_job_id: UUID,
    current: CurrentUser = Depends(require_admin),
    service: CollectionJobService = Depends(get_collection_job_service),
) -> CollectionJobDetailRead:
    return await service.get_detail(collection_job_id, actor=current.to_actor())


@router.post(
    "",
    response_model=CollectionJobDetailRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_discovery_job(
    payload: CollectionJobCreate,
    current: CurrentUser = Depends(require_admin),
    service: CollectionJobService = Depends(get_collection_job_service),
) -> CollectionJobDetailRead:
    # 1) Cria + commita o job (status='pending' por server_default).
    job = await service.create_discovery_job(
        olt_id=payload.olt_id,
        actor=current.to_actor(),
    )

    # 2) Enfileira a task. APÓS o commit, deliberadamente: o job tem
    # que existir no banco antes do worker tentar carrega-lo (sob eager,
    # o worker eh síncrono no mesmo processo).

    # Import tardio para evitar acoplamento de import time entre rotas
    # e Celery (api precisa do celery_app, mas não da task em si).
    from app.tasks.collection import run_discovery_job  # noqa: PLC0415

    try:
        run_discovery_job.delay(str(job.collection_job_id))
    except Exception as exc:
        # Aqui está a janela de órfão documentada.
        # Log para auditoria mas NÃO desfaz o commit do job (o operador pode
        # tentar relançar via novo POST quando o broker voltar).
        log.exception(
            "collection.enqueue_failed",
            collection_job_id=str(job.collection_job_id),
            error=str(exc),
        )

    # Em modo eager (testes), a task já rodou e o job está em estado
    # terminal. Em prod, status ainda é 'pending'. Buscamos detalhe
    # atualizado para devolver o estado real.
    return await service.get_detail(job.collection_job_id, actor=current.to_actor())
