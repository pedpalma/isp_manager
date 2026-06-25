# Repository de OpticalReading.
# CRITICAL: optical_reading e particionada por collected_at;
# toda query DEVE filtrar collected_at para que o planner faca partition pruning.

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.optical.models.optical_reading import OpticalReading

# Default conservador. 30 dias é a janela de troubleshooting típica e
# garante uso de pelo menos UMA partição mensal.
_DEFAULT_WINDOW_DAYS = 30


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)  # noqa: UP017


class OpticalReadingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_onu(
        self,
        *,
        onu_id: UUID,
        offset: int,
        limit: int,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> tuple[Sequence[OpticalReading], int]:
        """Devolve (itens da pagina, total na janela)."""
        if date_to is None:
            date_to = _utcnow()
        if date_from is None:
            date_from = date_to - timedelta(days=_DEFAULT_WINDOW_DAYS)

        base = (
            select(OpticalReading)
            .where(OpticalReading.onu_id == onu_id)
            .where(OpticalReading.collected_at >= date_from)
            .where(OpticalReading.collected_at < date_to)
        )
        # Ordenação DECRESCENTE
        items_stmt = base.order_by(OpticalReading.collected_at.desc()).offset(offset).limit(limit)
        items_result = await self._session.execute(items_stmt)
        items = items_result.scalars().all()

        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await self._session.execute(count_stmt)).scalar_one()

        return items, int(total)
