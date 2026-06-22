# Repository do CollectionJob.

# Filtro de OLT viva: JOIN com olt.deleted_at IS NULL em todas as leituras
# (mesmo padrão dos olt_children, com a diferença de que CollectionJob
# também tem olt_id direto, sem precisar de vários JOINs).

# add() faz session.add() + session.flush() para garantir que
# server_defaults sejam preenchidos (collection_job_id, status='pending',
# created_at).
# Service commita.

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.collection.enums import JobStatus
from app.domains.collection.models.collection_job import CollectionJob
from app.domains.inventory.models.olt import Olt


class CollectionJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, collection_job_id: UUID) -> CollectionJob | None:
        stmt = (
            select(CollectionJob)
            .join(Olt, Olt.olt_id == CollectionJob.olt_id)
            .where(
                CollectionJob.collection_job_id == collection_job_id,
                Olt.deleted_at.is_(None),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_page(
        self,
        *,
        limit: int,
        offset: int,
        olt_id: UUID | None,
        status_filter: JobStatus | None,
    ) -> tuple[Sequence[CollectionJob], int]:
        base = (
            select(CollectionJob)
            .join(Olt, Olt.olt_id == CollectionJob.olt_id)
            .where(Olt.deleted_at.is_(None))
        )
        if olt_id is not None:
            base = base.where(CollectionJob.olt_id == olt_id)
        if status_filter is not None:
            base = base.where(CollectionJob.status == status_filter)

        # Ordem alinhada com idx_collection_job_olt_status_created
        items_stmt = base.order_by(CollectionJob.created_at.desc()).offset(offset).limit(limit)
        items_result = await self._session.execute(items_stmt)
        items = items_result.scalars().all()

        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await self._session.execute(count_stmt)).scalar_one()

        return items, int(total)

    async def add(self, job: CollectionJob) -> None:
        self._session.add(job)
        await self._session.flush()
