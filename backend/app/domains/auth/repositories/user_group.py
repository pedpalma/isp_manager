# Repository do UserGroup.

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.models.user_group import UserGroup


class UserGroupRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_group_id: UUID) -> UserGroup | None:
        stmt = select(UserGroup).where(UserGroup.user_group_id == user_group_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> UserGroup | None:
        """Pre-check de unicidade TOTAL de `name`."""
        stmt = select(UserGroup).where(UserGroup.name == name)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_page(
        self,
        *,
        offset: int,
        limit: int,
        only_active: bool = False,
    ) -> tuple[Sequence[UserGroup], int]:
        base = select(UserGroup)
        count_q = select(func.count()).select_from(UserGroup)
        if only_active:
            base = base.where(UserGroup.active.is_(True))
            count_q = count_q.where(UserGroup.active.is_(True))

        page_q = base.order_by(UserGroup.name).offset(offset).limit(limit)
        items: Sequence[UserGroup] = (await self._session.execute(page_q)).scalars().all()
        total: int = (await self._session.execute(count_q)).scalar_one()
        return items, total

    async def add(self, group: UserGroup) -> None:
        self._session.add(group)
        await self._session.flush()

    async def flush(self) -> None:
        await self._session.flush()
