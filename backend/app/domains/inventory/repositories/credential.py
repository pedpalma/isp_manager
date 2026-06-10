# Repository do Credential.

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.inventory.models.credential import Credential


class CredentialRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # Leitura
    async def get_by_id(self, credential_id: UUID) -> Credential | None:
        stmt = select(Credential).where(Credential.credential_id == credential_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_page(
        self,
        *,
        offset: int,
        limit: int,
        only_active: bool = False,
        search: str | None = None,
    ) -> tuple[Sequence[Credential], int]:
        """Devolve (itens da página, total geral).
        `search` é case-insensitive e procura em `label` OU `username`
        (LIKE com `%texto%`)."""
        base_filter = select(Credential)
        count_query = select(func.count()).select_from(Credential)

        if only_active:
            base_filter = base_filter.where(Credential.active.is_(True))
            count_query = count_query.where(Credential.active.is_(True))

        if search:
            pattern = f"%{search.lower()}%"
            cond = or_(
                func.lower(Credential.label).like(pattern),
                func.lower(Credential.username).like(pattern),
            )
            base_filter = base_filter.where(cond)
            count_query = count_query.where(cond)

        page_query = base_filter.order_by(Credential.label).offset(offset).limit(limit)

        items_result = await self._session.execute(page_query)
        items: Sequence[Credential] = items_result.scalars().all()

        total_result = await self._session.execute(count_query)
        total: int = total_result.scalar_one()

        return items, total

    # Escrita
    async def add(self, credential: Credential) -> None:
        """Adiciona à sessão e força flush para popular o `credential_id`
        gerado pelo Postgres. NÃO commita."""
        self._session.add(credential)
        await self._session.flush()

    async def flush(self) -> None:
        """Reflete mudanças pendentes (UPDATEs feitos manipulando os
        atributos do objeto carregado pela sessão)."""
        await self._session.flush()
