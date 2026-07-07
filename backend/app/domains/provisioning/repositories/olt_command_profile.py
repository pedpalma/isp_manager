# Repository de OltCommandProfile

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.inventory.enums import AccessProtocol
from app.domains.provisioning.models.olt_command_profile import OltCommandProfile


class OltCommandProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, obj: OltCommandProfile) -> None:
        self._session.add(obj)
        await self._session.flush()

    async def flush(self) -> None:
        await self._session.flush()

    async def get_by_id(self, olt_command_profile_id: UUID) -> OltCommandProfile | None:
        stmt = select(OltCommandProfile).where(
            OltCommandProfile.olt_command_profile_id == olt_command_profile_id
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_key(
        self,
        *,
        olt_model_id: UUID,
        firmware_version: str,
        access_protocol: AccessProtocol,
    ) -> OltCommandProfile | None:
        """Pré-check de unicidade TOTAL uq_olt_command_profile."""
        stmt = select(OltCommandProfile).where(
            OltCommandProfile.olt_model_id == olt_model_id,
            OltCommandProfile.firmware_version == firmware_version,
            OltCommandProfile.access_protocol == access_protocol,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_page(
        self,
        *,
        offset: int,
        limit: int,
        olt_model_id: UUID | None = None,
        access_protocol: AccessProtocol | None = None,
        active: bool | None = None,
    ) -> tuple[Sequence[OltCommandProfile], int]:
        base = select(OltCommandProfile)
        if olt_model_id is not None:
            base = base.where(OltCommandProfile.olt_model_id == olt_model_id)
        if access_protocol is not None:
            base = base.where(OltCommandProfile.access_protocol == access_protocol)
        if active is not None:
            base = base.where(OltCommandProfile.active.is_(active))

        # Total
        count_stmt = select(func.count()).select_from(base.subquery())
        total = int((await self._session.execute(count_stmt)).scalar_one())

        # Página
        items_stmt = (
            base.order_by(
                OltCommandProfile.olt_model_id.asc(),
                OltCommandProfile.firmware_version.asc(),
                OltCommandProfile.access_protocol.asc(),
            )
            .offset(offset)
            .limit(limit)
        )
        items = (await self._session.execute(items_stmt)).scalars().all()
        return items, total
