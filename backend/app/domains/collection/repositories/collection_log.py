# Repository do CollectionLog.

# Acessado apenas como filho de um collection_job (1:N): São listados todos
# os logs daquele job. Sem CRUD direto via API: o worker escreve via
# session sync, está camada é somente leitura no contexto da API.

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.collection.models.collection_log import CollectionLog


class CollectionLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_job(self, collection_job_id: UUID) -> Sequence[CollectionLog]:
        stmt = (
            select(CollectionLog)
            .where(CollectionLog.collection_job_id == collection_job_id)
            .order_by(CollectionLog.executed_at.asc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
