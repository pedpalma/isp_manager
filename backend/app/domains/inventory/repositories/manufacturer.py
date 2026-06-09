# Repository do Manufacturer.
#
# Camada que fala com o banco. Regras importantes:
#   - NÃO contém regra de negócio (vai no Service).
#   - NÃO chama commit/rollback. Quem decide o limite da transação é o
#     Service. O repositório só faz add/flush e queries.
#   - Levanta erros do SQLAlchemy (IntegrityError etc.); o Service traduz
#     para erros de domínio.

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.inventory.models.manufacturer import Manufacturer


class ManufacturerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ----- Leitura -----

    async def get_by_id(self, manufacturer_id: UUID) -> Manufacturer | None:
        stmt = select(Manufacturer).where(Manufacturer.manufacturer_id == manufacturer_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Manufacturer | None:
        stmt = select(Manufacturer).where(Manufacturer.slug == slug)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_page(
        self,
        *,
        offset: int,
        limit: int,
        only_active: bool = False,
        search: str | None = None,
    ) -> tuple[Sequence[Manufacturer], int]:
        """Devolve (itens da página, total geral).

        Duas queries: a primeira com OFFSET/LIMIT, a segunda COUNT(*).
        Para tabelas de catálogo (poucas linhas) é aceitável. Em tabelas
        de alto volume, reavaliar (ex.: cursor pagination, COUNT
        aproximado via pg_class.reltuples).
        """
        base_filter = select(Manufacturer)
        count_query = select(func.count()).select_from(Manufacturer)

        if only_active:
            base_filter = base_filter.where(Manufacturer.active.is_(True))
            count_query = count_query.where(Manufacturer.active.is_(True))

        if search:
            pattern = f"%{search.lower()}%"
            base_filter = base_filter.where(func.lower(Manufacturer.name).like(pattern))
            count_query = count_query.where(func.lower(Manufacturer.name).like(pattern))

        page_query = base_filter.order_by(Manufacturer.name).offset(offset).limit(limit)

        items_result = await self._session.execute(page_query)
        items: Sequence[Manufacturer] = items_result.scalars().all()

        total_result = await self._session.execute(count_query)
        total: int = total_result.scalar_one()

        return items, total

    # ----- Escrita -----

    async def add(self, manufacturer: Manufacturer) -> None:
        """Adiciona à sessão e força flush para popular o `manufacturer_id`
        gerado pelo Postgres. NÃO commita: quem decide é o Service."""
        self._session.add(manufacturer)
        await self._session.flush()

    async def flush(self) -> None:
        """Atalho para refletir mudanças pendentes (UPDATEs feitos
        manipulando os atributos do objeto carregado pela sessão)."""
        await self._session.flush()
