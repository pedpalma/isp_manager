# Service de OltCommandProfile.

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.pagination import Page, PageParams
from app.domains.inventory.enums import AccessProtocol
from app.domains.inventory.models.olt_model import OltModel
from app.domains.provisioning.exceptions import (
    OltCommandProfileConflict,
    OltCommandProfileNotFound,
    OltModelReferenceInvalid,
)
from app.domains.provisioning.models.olt_command_profile import OltCommandProfile
from app.domains.provisioning.repositories.olt_command_profile import (
    OltCommandProfileRepository,
)
from app.domains.provisioning.schemas.olt_command_profile import (
    OltCommandProfileCreate,
    OltCommandProfileRead,
    OltCommandProfileUpdate,
)

log = structlog.get_logger(__name__)


class OltCommandProfileService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = OltCommandProfileRepository(session)

    # Leitura
    async def get(
        self,
        olt_command_profile_id: UUID,
        *,
        actor: Actor,
    ) -> OltCommandProfileRead:
        del actor
        obj = await self._repo.get_by_id(olt_command_profile_id)
        if obj is None:
            raise OltCommandProfileNotFound(olt_command_profile_id)
        return OltCommandProfileRead.model_validate(obj)

    async def list_page(
        self,
        *,
        params: PageParams,
        olt_model_id: UUID | None,
        access_protocol: AccessProtocol | None,
        active: bool | None,
        actor: Actor,
    ) -> Page[OltCommandProfileRead]:
        del actor
        items, total = await self._repo.list_page(
            offset=params.offset,
            limit=params.limit,
            olt_model_id=olt_model_id,
            access_protocol=access_protocol,
            active=active,
        )
        return Page[OltCommandProfileRead](
            items=[OltCommandProfileRead.model_validate(i) for i in items],
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    # Escrita
    async def create(
        self,
        payload: OltCommandProfileCreate,
        *,
        actor: Actor,
    ) -> OltCommandProfileRead:
        await self._validate_olt_model(payload.olt_model_id)

        existing = await self._repo.get_by_key(
            olt_model_id=payload.olt_model_id,
            firmware_version=payload.firmware_version,
            access_protocol=payload.access_protocol,
        )
        if existing is not None:
            raise OltCommandProfileConflict(
                olt_model_id=payload.olt_model_id,
                firmware_version=payload.firmware_version,
                access_protocol=payload.access_protocol.value,
            )

        obj = OltCommandProfile(
            olt_model_id=payload.olt_model_id,
            firmware_version=payload.firmware_version,
            access_protocol=payload.access_protocol,
            version_constraint=payload.version_constraint,
            parser_profile=payload.parser_profile,
            active=payload.active,
        )
        try:
            await self._repo.add(obj)
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise OltCommandProfileConflict(
                olt_model_id=payload.olt_model_id,
                firmware_version=payload.firmware_version,
                access_protocol=payload.access_protocol.value,
            ) from exc

        await self._session.refresh(obj)
        log.info(
            "olt_command_profile.created",
            olt_command_profile_id=str(obj.olt_command_profile_id),
            olt_model_id=str(obj.olt_model_id),
            firmware_version=obj.firmware_version,
            access_protocol=obj.access_protocol.value,
            actor=str(actor),
        )
        return OltCommandProfileRead.model_validate(obj)

    async def update(
        self,
        olt_command_profile_id: UUID,
        payload: OltCommandProfileUpdate,
        *,
        actor: Actor,
    ) -> OltCommandProfileRead:
        obj = await self._repo.get_by_id(olt_command_profile_id)
        if obj is None:
            raise OltCommandProfileNotFound(olt_command_profile_id)

        data = payload.model_dump(exclude_unset=True)
        if not data:
            return OltCommandProfileRead.model_validate(obj)

        for field, value in data.items():
            setattr(obj, field, value)

        await self._session.commit()
        await self._session.refresh(obj)

        log.info(
            "olt_command_profile.updated",
            olt_command_profile_id=str(obj.olt_command_profile_id),
            fields=list(data.keys()),
            actor=str(actor),
        )
        return OltCommandProfileRead.model_validate(obj)

    # Helpers
    async def _validate_olt_model(self, olt_model_id: UUID) -> None:
        stmt = select(OltModel.olt_model_id).where(
            OltModel.olt_model_id == olt_model_id,
            OltModel.active.is_(True),
        )
        if (await self._session.execute(stmt)).scalar_one_or_none() is None:
            raise OltModelReferenceInvalid(olt_model_id)
