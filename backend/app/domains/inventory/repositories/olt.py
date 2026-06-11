# Repository da OLT.

# Regras (iguais ao gabarito):
# - NÃO contém regra de negócio (vai no Service).
# - NÃO chama commit/rollback. Só add/flush e queries.
# - Levanta erros do SQLAlchemy; o Service traduz para erros de domínio.

# Ponto crítico desta camada: TODA leitura relevante para unicidade e
# para detalhe filtra `deleted_at IS NULL`. Uma OLT soft-deletada é
# tratada como inexistente e libera name e (ip, porta), em linha com as
# unicidades parciais do DDL.

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.inventory.models.olt import Olt


class OltRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # Leitura
    async def get_by_id(self, olt_id: UUID) -> Olt | None:
        """Detalhe de OLT viva. Soft-deletada -> None (vira 404 no service)."""
        stmt = select(Olt).where(
            Olt.olt_id == olt_id,
            Olt.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_by_name(self, name: str) -> Olt | None:
        """Pré-check de unicidade de name entre OLTs vivas."""
        stmt = select(Olt).where(
            Olt.name == name,
            Olt.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_by_ip_port(self, ip: str, management_port: int) -> Olt | None:
        """Pré-check de unicidade do par (ip, porta) entre OLTs vivas."""
        stmt = select(Olt).where(
            Olt.ip == ip,
            Olt.management_port == management_port,
            Olt.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def has_active_for_credential(self, credential_id: UUID) -> bool:
        """True se existe ALGUMA OLT viva (deleted_at IS NULL) usando esta
        credencial, independente do flag `active`. Suporta a regra herdada
        do Marco 10: credencial em uso não pode ser desativada.
        """
        stmt = (
            select(func.count())
            .select_from(Olt)
            .where(
                Olt.credential_id == credential_id,
                Olt.deleted_at.is_(None),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one() > 0

    async def list_page(
        self,
        *,
        offset: int,
        limit: int,
        only_active: bool = False,
        search: str | None = None,
    ) -> tuple[Sequence[Olt], int]:
        """Devolve (itens da página, total geral). Sempre exclui soft-deletadas.

        only_active: filtra adicionalmente pelo flag `active`.
        search: case-insensitive em name OU hostname.
        """
        base_filter = select(Olt).where(Olt.deleted_at.is_(None))
        count_query = select(func.count()).select_from(Olt).where(Olt.deleted_at.is_(None))

        if only_active:
            base_filter = base_filter.where(Olt.active.is_(True))
            count_query = count_query.where(Olt.active.is_(True))

        if search:
            pattern = f"%{search.lower()}%"
            cond = or_(
                func.lower(Olt.name).like(pattern),
                func.lower(func.coalesce(Olt.hostname, "")).like(pattern),
            )
            base_filter = base_filter.where(cond)
            count_query = count_query.where(cond)

        page_query = base_filter.order_by(Olt.name).offset(offset).limit(limit)

        items_result = await self._session.execute(page_query)
        items: Sequence[Olt] = items_result.scalars().all()

        total_result = await self._session.execute(count_query)
        total: int = total_result.scalar_one()

        return items, total

    # Escrita
    async def add(self, olt: Olt) -> None:
        """Adiciona à sessão e flusha para popular olt_id e connection_status
        (via RETURNING). NÃO commita: quem decide é o Service."""
        self._session.add(olt)
        await self._session.flush()

    async def flush(self) -> None:
        await self._session.flush()
