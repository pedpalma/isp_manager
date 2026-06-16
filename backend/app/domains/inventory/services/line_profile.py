# Service do Line Profile.

from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.logging import get_logger
from app.core.pagination import Page, PageParams
from app.domains.inventory.exceptions import (
    LineProfileConflict,
    LineProfileNotFound,
    OltReferenceInvalid,
)
from app.domains.inventory.models.line_profile import LineProfile
from app.domains.inventory.repositories.line_profile import LineProfileRepository
from app.domains.inventory.repositories.olt import OltRepository
from app.domains.inventory.schemas.line_profile import (
    LineProfileCreate,
    LineProfileRead,
    LineProfileUpdate,
)

log = get_logger(__name__)


class LineProfileService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = LineProfileRepository(session)

    async def get(self, line_profile_id: UUID, *, actor: Actor) -> LineProfileRead:
        del actor
        lp = await self._repo.get_by_id(line_profile_id)
        if lp is None:
            raise LineProfileNotFound(line_profile_id)
        return LineProfileRead.model_validate(lp)

    async def list_for_olt(
        self, olt_id: UUID, params: PageParams, *, actor: Actor
    ) -> Page[LineProfileRead]:
        del actor
        items, total = await self._repo.list_for_olt(
            olt_id, offset=params.offset, limit=params.limit
        )
        return Page[LineProfileRead](
            items=[LineProfileRead.model_validate(lp) for lp in items],
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    async def create(self, payload: LineProfileCreate, *, actor: Actor) -> LineProfileRead:
        olt_repo = OltRepository(self._session)
        olt = await olt_repo.get_by_id(payload.olt_id)
        if olt is None:
            raise OltReferenceInvalid(payload.olt_id)

        existing = await self._repo.get_by_olt_name_version(
            payload.olt_id, payload.name, payload.version
        )
        if existing is not None:
            raise LineProfileConflict(payload.olt_id, payload.name, payload.version)

        lp = LineProfile(
            olt_id=payload.olt_id,
            name=payload.name,
            version=payload.version,
            logical_name=payload.logical_name,
            upstream_bandwidth=payload.upstream_bandwidth,
            downstream_bandwidth=payload.downstream_bandwidth,
            raw_config=payload.raw_config,
            active=payload.active,
        )
        try:
            await self._repo.add(lp)
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise LineProfileConflict(payload.olt_id, payload.name, payload.version) from exc

        log.info(
            "line_profile.created",
            line_profile_id=str(lp.line_profile_id),
            olt_id=str(lp.olt_id),
            name=lp.name,
            version=lp.version,
            actor=str(actor),
        )
        return LineProfileRead.model_validate(lp)

    async def update(
        self, line_profile_id: UUID, payload: LineProfileUpdate, *, actor: Actor
    ) -> LineProfileRead:
        lp = await self._repo.get_by_id(line_profile_id)
        if lp is None:
            raise LineProfileNotFound(line_profile_id)

        data = payload.model_dump(exclude_unset=True)
        if not data:
            return LineProfileRead.model_validate(lp)

        for field, value in data.items():
            setattr(lp, field, value)

        await self._session.commit()
        await self._session.refresh(lp)

        log.info(
            "line_profile.updated",
            line_profile_id=str(lp.line_profile_id),
            fields=list(data.keys()),
            actor=str(actor),
        )
        return LineProfileRead.model_validate(lp)
