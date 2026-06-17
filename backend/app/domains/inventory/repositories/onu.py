# Repository da ONU.
# Regras do gabarito:
# - Sem regra de negócio (vai no Service).
# - Nao chama commit/rollback. Só add/flush e queries.
# - Levanta erros do SQLAlchemy; o Service traduz para erros de domínio.

# Ponto desta camada: a ONU é soft-delete de primeira classe (como a OLT).
# Toda leitura relevante filtra `deleted_at IS NULL`. "Vivo" da ONU e o PRÓPRIO
# deleted_at, NÃO herdado da OLT por JOIN. A proteção de "PON viva" acontece na CRIAÇÃO.

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.inventory.models.onu import Onu
from app.domains.inventory.models.onu_runtime_state import OnuRuntimeState


class OnuRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # Leitura
    async def get_by_id(self, onu_id: UUID) -> Onu | None:
        """Detalhe de ONU viva. Soft-deletada -> None (vira 404 no service)."""
        stmt = select(Onu).where(
            Onu.onu_id == onu_id,
            Onu.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_by_serial(self, serial: str) -> Onu | None:
        """Pre-check da unicidade de serial entre ONUs vivas (uq_onu_serial_active)."""
        stmt = select(Onu).where(
            Onu.serial == serial,
            Onu.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_by_pon_index(
        self,
        pon_port_id: UUID,
        onu_index: int,
        *,
        exclude_onu_id: UUID | None = None,
    ) -> Onu | None:
        """Pre-check da unicidade (pon_port_id, onu_index) entre ONUs vivas
        (uq_onu_index_per_pon_active). So faz sentido com onu_index != None.
        `exclude_onu_id` ignora a própria ONU no PATCH."""
        stmt = select(Onu).where(
            Onu.pon_port_id == pon_port_id,
            Onu.onu_index == onu_index,
            Onu.deleted_at.is_(None),
        )
        if exclude_onu_id is not None:
            stmt = stmt.where(Onu.onu_id != exclude_onu_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_page(
        self,
        *,
        offset: int,
        limit: int,
        pon_port_id: UUID | None = None,
        serial: str | None = None,
    ) -> tuple[Sequence[Onu], int]:
        """Devolve (itens da pagina, total geral). Sempre exclui soft-deletadas.

        Filtros opcionais e combináveis:
        - pon_port_id: ONUs daquela PON.
        - serial: busca parcial case-insensitive (ILIKE). Acelerada pelo índice trigram idx_onu_serial_trgm."""
        base = select(Onu).where(Onu.deleted_at.is_(None))
        count_query = select(func.count()).select_from(Onu).where(Onu.deleted_at.is_(None))

        if pon_port_id is not None:
            base = base.where(Onu.pon_port_id == pon_port_id)
            count_query = count_query.where(Onu.pon_port_id == pon_port_id)

        if serial:
            pattern = f"%{serial}%"
            base = base.where(Onu.serial.ilike(pattern))
            count_query = count_query.where(Onu.serial.ilike(pattern))

        page_query = base.order_by(Onu.serial.asc()).offset(offset).limit(limit)

        items_result = await self._session.execute(page_query)
        items: Sequence[Onu] = items_result.scalars().all()

        total_result = await self._session.execute(count_query)
        total: int = total_result.scalar_one()

        return items, total

    async def get_runtime(self, onu_id: UUID) -> OnuRuntimeState | None:
        """Le o estado operacional 1:1. Criado pela trigger no INSERT da ONU."""
        stmt = select(OnuRuntimeState).where(OnuRuntimeState.onu_id == onu_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    # Escrita
    async def add(self, onu: Onu) -> None:
        """Adiciona a sessão e flusha. O flush:
        - popula onu_id / provisioned / timestamps via RETURNING;
        - DISPARA a trigger AFTER INSERT que cria a linha de onu_runtime_state
        (na mesma transação). NAO commita: quem decide e o Service."""
        self._session.add(onu)
        await self._session.flush()

    async def flush(self) -> None:
        await self._session.flush()
