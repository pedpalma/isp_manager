# Repository do AppUser
from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.models.app_user import AppUser


class AppUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, app_user_id: UUID) -> AppUser | None:
        stmt = select(AppUser).where(AppUser.app_user_id == app_user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> AppUser | None:
        """Usado no login e como pre-check de unicidade de `username`."""
        stmt = select(AppUser).where(AppUser.username == username)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> AppUser | None:
        """Pre-check de unicidade TOTAL de `Email`."""
        stmt = select(AppUser).where(AppUser.email == email)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_page(
        self,
        *,
        offset: int,
        limit: int,
        only_active: bool = False,
        user_group_id: UUID | None = None,
        search: str | None = None,
    ) -> tuple[Sequence[AppUser], int]:
        """`search` case-insensitive  em username OU email."""
        base = select(AppUser)
        count_q = select(func.count()).select_from(AppUser)

        if only_active:
            base = base.where(AppUser.active.is_(True))
            count_q = count_q.where(AppUser.active.is_(True))
        if user_group_id is not None:
            base = base.where(AppUser.user_group_id == user_group_id)
            count_q = count_q.where(AppUser.user_group_id == user_group_id)
        if search:
            pattern = f"%{search.lower()}%"
            cond = or_(
                func.lower(AppUser.username).like(pattern),
                func.lower(AppUser.email).like(pattern),
            )
            base = base.where(cond)
            count_q = count_q.where(cond)

        page_q = base.order_by(AppUser.username).offset(offset).limit(limit)
        items: Sequence[AppUser] = (await self._session.execute(page_q)).scalars().all()
        total: int = (await self._session.execute(count_q)).scalar_one()
        return items, total

    async def add(self, user: AppUser) -> None:
        self._session.add(user)
        await self._session.flush()

    async def flush(self) -> None:
        await self._session.flush()
