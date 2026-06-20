# Service do UserGroup.

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.logging import get_logger
from app.domains.auth.exceptions import UserGroupConflict, UserGroupNotFound
from app.domains.auth.models.user_group import UserGroup
from app.domains.auth.repositories.user_group import UserGroupRepository
from app.domains.auth.schemas.user_group import UserGroupCreate, UserGroupUpdate

log = get_logger(__name__)


class UserGroupService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = UserGroupRepository(session)

    async def get(self, user_group_id: UUID, *, actor: Actor) -> UserGroup:
        del actor
        g = await self._repo.get_by_id(user_group_id)
        if g is None:
            raise UserGroupNotFound(user_group_id)
        return g

    async def list_page(
        self,
        *,
        offset: int,
        limit: int,
        only_active: bool = False,
        actor: Actor,
    ) -> tuple[Sequence[UserGroup], int]:
        del actor
        return await self._repo.list_page(offset=offset, limit=limit, only_active=only_active)

    async def create(self, data: UserGroupCreate, *, actor: Actor) -> UserGroup:
        # Unicidade única (name): pre-check + captura de IntegrityError genérica.
        if await self._repo.get_by_name(data.name) is not None:
            raise UserGroupConflict(data.name)

        g = UserGroup(
            name=data.name,
            permissions_json=data.permissions_json,
            active=data.active,
        )
        self._session.add(g)
        try:
            await self._session.flush()
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise UserGroupConflict(data.name) from exc

        log.info(
            "user_group.created",
            user_group_id=str(g.user_group_id),
            name=g.name,
            actor=actor.username,
        )
        return g

    async def update(
        self, user_group_id: UUID, data: UserGroupUpdate, *, actor: Actor
    ) -> UserGroup:
        g = await self._repo.get_by_id(user_group_id)
        if g is None:
            raise UserGroupNotFound(user_group_id)

        payload = data.model_dump(exclude_unset=True)
        if not payload:
            return g

        # `name` é imutável (fora do Update). Nenhum campo mutável colide com
        # unicidade, logo nao ha try/except aqui (update_no_try_except).
        for field, value in payload.items():
            setattr(g, field, value)

        await self._repo.flush()
        await self._session.commit()

        log.info(
            "user_group.updated",
            user_group_id=str(g.user_group_id),
            fields=list(payload.keys()),
            actor=actor.username,
        )
        return g
