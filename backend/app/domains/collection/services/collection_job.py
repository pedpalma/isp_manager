# Service do CollectionJob.

# Responsabilidades:
# - validar OLT viva antes de criar job (BadRequest 400 se ausente)
# - inserir o job (status='pending' por server_default)
# - tratar conflito da unicidade parcial uq_collection_job_running (Conflict 409)
# - oferecer leitura paginada e detalhe com logs embutidos

# A rota é quem chama task.delay() APÓS commit. Janela de órfão:
# commit ok + enqueue falhando deixa o job em 'pending' para sempre.

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.pagination import Page, PageParams
from app.domains.collection.enums import JOB_TYPE_DISCOVERY, JobStatus, JobTriggerType
from app.domains.collection.exceptions import (
    CollectionJobConflict,
    CollectionJobNotFound,
    OltReferenceInvalid,
)
from app.domains.collection.models.collection_job import CollectionJob
from app.domains.collection.repositories.collection_job import (
    CollectionJobRepository,
)
from app.domains.collection.repositories.collection_log import (
    CollectionLogRepository,
)
from app.domains.collection.schemas.collection_job import (
    CollectionJobDetailRead,
    CollectionJobRead,
)
from app.domains.collection.schemas.collection_log import CollectionLogRead
from app.domains.inventory.repositories.olt import OltRepository

log = structlog.get_logger(__name__)

# Nome do índice único parcial criado na migration 0003.
_UQ_RUNNING = "uq_collection_job_running"


def _violated_constraint(orig: str) -> str | None:
    if _UQ_RUNNING in orig:
        return _UQ_RUNNING
    return None


class CollectionJobService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = CollectionJobRepository(session)
        self._log_repo = CollectionLogRepository(session)

    async def get_detail(self, collection_job_id: UUID, *, actor: Actor) -> CollectionJobDetailRead:
        del actor
        job = await self._repo.get_by_id(collection_job_id)
        if job is None:
            raise CollectionJobNotFound(collection_job_id)
        logs = await self._log_repo.list_for_job(collection_job_id)
        return CollectionJobDetailRead(
            **CollectionJobRead.model_validate(job).model_dump(),
            logs=[CollectionLogRead.model_validate(entry) for entry in logs],
        )

    async def list_page(
        self,
        *,
        params: PageParams,
        olt_id: UUID | None,
        status_filter: JobStatus | None,
        actor: Actor,
    ) -> Page[CollectionJobRead]:
        del actor
        items, total = await self._repo.list_page(
            limit=params.limit,
            offset=params.offset,
            olt_id=olt_id,
            status_filter=status_filter,
        )
        return Page[CollectionJobRead](
            items=[CollectionJobRead.model_validate(j) for j in items],
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    async def create_discovery_job(
        self,
        *,
        olt_id: UUID,
        actor: Actor,
    ) -> CollectionJobDetailRead:
        """Cria um job de descoberta. NÃO enfileira a task: isso é
        responsabilidade da rota, após o commit, para que a transação
        de banco seja a fonte da verdade da existência do job."""
        olt = await OltRepository(self._session).get_by_id(olt_id)
        if olt is None:
            raise OltReferenceInvalid(olt_id)

        job = CollectionJob(
            olt_id=olt_id,
            requested_by_user_id=actor.actor_id,
            job_type=JOB_TYPE_DISCOVERY,
            trigger_type=JobTriggerType.MANUAL,
            payload={},
        )
        try:
            await self._repo.add(job)
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            constraint = _violated_constraint(str(exc.orig))
            if constraint == _UQ_RUNNING:
                raise CollectionJobConflict(olt_id, JOB_TYPE_DISCOVERY) from exc
            raise

        # Refresh para popular server_defaults (collection_job_id, status,
        # created_at).
        await self._session.refresh(job)

        log.info(
            "collection_job.created",
            collection_job_id=str(job.collection_job_id),
            olt_id=str(olt_id),
            job_type=JOB_TYPE_DISCOVERY,
            actor=str(actor),
        )

        return CollectionJobDetailRead(
            **CollectionJobRead.model_validate(job).model_dump(),
            logs=[],
        )
