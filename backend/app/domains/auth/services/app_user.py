# Service do AppUser.

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.logging import get_logger
from app.domains.auth.exceptions import (
    AppUserEmailConflict,
    AppUserNotFound,
    AppUserUsernameConflict,
    UserGroupReferenceInvalid,
)
from app.domains.auth.models.app_user import AppUser
from app.domains.auth.repositories.app_user import AppUserRepository
from app.domains.auth.repositories.user_group import UserGroupRepository
from app.domains.auth.schemas.app_user import AppUserCreate, AppUserUpdate
from app.domains.auth.security import hash_password

log = get_logger(__name__)

# Duas unicidades TOTAIS concorrentes: inspecionamos o nome da constraint na
# IntegrityError (padrão olt/onu). Constantes no topo, conforme convenção.
_UQ_USERNAME = "uq_app_user_username"
_UQ_EMAIL = "uq_app_user_email"


def _violated_constraint(orig_msg: str) -> str | None:
    for name in (_UQ_USERNAME, _UQ_EMAIL):
        if name in orig_msg:
            return name
    return None


class AppUserService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = AppUserRepository(session)
        self._groups = UserGroupRepository(session)

    async def get(self, app_user_id: UUID, *, actor: Actor) -> AppUser:
        del actor
        u = await self._repo.get_by_id(app_user_id)
        if u is None:
            raise AppUserNotFound(app_user_id)
        return u

    async def list_page(
        self,
        *,
        offset: int,
        limit: int,
        only_active: bool = False,
        user_group_id: UUID | None = None,
        search: str | None = None,
        actor: Actor,
    ) -> tuple[Sequence[AppUser], int]:
        del actor
        return await self._repo.list_page(
            offset=offset,
            limit=limit,
            only_active=only_active,
            user_group_id=user_group_id,
            search=search,
        )

    async def _validate_group_alive(self, user_group_id: UUID) -> None:
        g = await self._groups.get_by_id(user_group_id)
        if g is None or not g.active:
            raise UserGroupReferenceInvalid(user_group_id)

    async def create(self, data: AppUserCreate, *, actor: Actor) -> AppUser:
        # 1. valida o grupo (FK invalida = 400; grupo inativo também)
        await self._validate_group_alive(data.user_group_id)

        # 2. pre-check das duas unicidades
        if await self._repo.get_by_username(data.username) is not None:
            raise AppUserUsernameConflict(data.username)
        if await self._repo.get_by_email(data.email) is not None:
            raise AppUserEmailConflict(data.email)

        # 3. hash da senha em claro (nunca persistimos o claro)
        user = AppUser(
            user_group_id=data.user_group_id,
            username=data.username,
            email=data.email,
            password_hash=hash_password(data.password),
            active=data.active,
            must_change_password=data.must_change_password,
        )
        self._session.add(user)
        try:
            await self._session.flush()
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            violated = _violated_constraint(str(exc.orig))
            if violated == _UQ_EMAIL:
                raise AppUserEmailConflict(data.email) from exc
            raise AppUserUsernameConflict(data.username) from exc

        # Recarrega o objeto: colunas nullable sem server_default (last_login_at)
        # não foram carregadas no INSERT e ficariam expiradas. Acessa-las na
        # serialização (AppUserRead) dispararia lazy-load assíncrono fora do
        # greenlet e quebraria. O refresh traz todas as colunas como valores
        # reais, igual ao caminho do GET.
        await self._session.refresh(user)

        log.info(
            "app_user.created",
            app_user_id=str(user.app_user_id),
            username=user.username,
            user_group_id=str(user.user_group_id),
            actor=actor.username,
        )
        return user

    async def update(self, app_user_id: UUID, data: AppUserUpdate, *, actor: Actor) -> AppUser:
        user = await self._repo.get_by_id(app_user_id)
        if user is None:
            raise AppUserNotFound(app_user_id)

        payload = data.model_dump(exclude_unset=True)
        if not payload:
            return user

        if "user_group_id" in payload:
            await self._validate_group_alive(payload["user_group_id"])

        # `email` é mutável e único TOTAL: pre-check ignorando o próprio
        # registro. `username` é imutável (fora do Update), não precisa pre-check.
        if "email" in payload:
            existing = await self._repo.get_by_email(payload["email"])
            if existing is not None and existing.app_user_id != user.app_user_id:
                raise AppUserEmailConflict(payload["email"])

        for field, value in payload.items():
            setattr(user, field, value)

        try:
            await self._repo.flush()
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            # Corrida no email (entre pre-check e commit). username imutável,
            # então a única colisão possível aqui é o email.
            raise AppUserEmailConflict(payload.get("email", "")) from exc

        # Mesmo motivo do create: garante objeto totalmente carregado antes da
        # serialização em AppUserRead.
        await self._session.refresh(user)

        log.info(
            "app_user.updated",
            app_user_id=str(user.app_user_id),
            fields=list(payload.keys()),
            actor=actor.username,
        )
        return user
