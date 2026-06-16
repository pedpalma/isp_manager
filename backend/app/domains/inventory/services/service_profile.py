# Service do Service Profile.

from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.logging import get_logger
from app.core.pagination import Page, PageParams
from app.domains.inventory.exceptions import (
    OltReferenceInvalid,
    ServiceProfileConflict,
    ServiceProfileNotFound,
)
from app.domains.inventory.models.service_profile import ServiceProfile
from app.domains.inventory.repositories.olt import OltRepository
from app.domains.inventory.repositories.service_profile import (
    ServiceProfileRepository,
)
from app.domains.inventory.schemas.service_profile import (
    ServiceProfileCreate,
    ServiceProfileRead,
    ServiceProfileUpdate,
)

log = get_logger(__name__)


class ServiceProfileService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = ServiceProfileRepository(session)

    async def get(self, service_profile_id: UUID, *, actor: Actor) -> ServiceProfileRead:
        del actor
        sp = await self._repo.get_by_id(service_profile_id)
        if sp is None:
            raise ServiceProfileNotFound(service_profile_id)
        return ServiceProfileRead.model_validate(sp)

    async def list_for_olt(
        self, olt_id: UUID, params: PageParams, *, actor: Actor
    ) -> Page[ServiceProfileRead]:
        del actor
        items, total = await self._repo.list_for_olt(
            olt_id, offset=params.offset, limit=params.limit
        )
        return Page[ServiceProfileRead](
            items=[ServiceProfileRead.model_validate(sp) for sp in items],
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    async def create(self, payload: ServiceProfileCreate, *, actor: Actor) -> ServiceProfileRead:
        olt_repo = OltRepository(self._session)
        olt = await olt_repo.get_by_id(payload.olt_id)
        if olt is None:
            raise OltReferenceInvalid(payload.olt_id)

        existing = await self._repo.get_by_olt_name_version(
            payload.olt_id, payload.name, payload.version
        )
        if existing is not None:
            raise ServiceProfileConflict(payload.olt_id, payload.name, payload.version)

        sp = ServiceProfile(
            olt_id=payload.olt_id,
            name=payload.name,
            version=payload.version,
            logical_name=payload.logical_name,
            raw_config=payload.raw_config,
            active=payload.active,
        )
        try:
            await self._repo.add(sp)
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ServiceProfileConflict(payload.olt_id, payload.name, payload.version) from exc

        log.info(
            "service_profile.created",
            service_profile_id=str(sp.service_profile_id),
            olt_id=str(sp.olt_id),
            name=sp.name,
            version=sp.version,
            actor=str(actor),
        )
        return ServiceProfileRead.model_validate(sp)

    async def update(
        self,
        service_profile_id: UUID,
        payload: ServiceProfileUpdate,
        *,
        actor: Actor,
    ) -> ServiceProfileRead:
        sp = await self._repo.get_by_id(service_profile_id)
        if sp is None:
            raise ServiceProfileNotFound(service_profile_id)

        data = payload.model_dump(exclude_unset=True)
        if not data:
            return ServiceProfileRead.model_validate(sp)

        for field, value in data.items():
            setattr(sp, field, value)

        await self._session.commit()
        await self._session.refresh(sp)

        log.info(
            "service_profile.updated",
            service_profile_id=str(sp.service_profile_id),
            fields=list(data.keys()),
            actor=str(actor),
        )
        return ServiceProfileRead.model_validate(sp)
