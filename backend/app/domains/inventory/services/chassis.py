# Service do Chassis.

from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.logging import get_logger
from app.core.pagination import Page, PageParams
from app.domains.inventory.exceptions import (
    ChassisConflict,
    ChassisNotFound,
    OltReferenceInvalid,
)
from app.domains.inventory.models.chassis import Chassis
from app.domains.inventory.repositories.chassis import ChassisRepository
from app.domains.inventory.repositories.olt import OltRepository
from app.domains.inventory.schemas.chassis import (
    ChassisCreate,
    ChassisRead,
    ChassisUpdate,
)

log = get_logger(__name__)


class ChassisService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = ChassisRepository(session)

    async def get(self, chassis_id: UUID, *, actor: Actor) -> ChassisRead:
        del actor
        chassis = await self._repo.get_by_id(chassis_id)
        if chassis is None:
            raise ChassisNotFound(chassis_id)
        return ChassisRead.model_validate(chassis)

    async def list_for_olt(
        self,
        olt_id: UUID,
        params: PageParams,
        *,
        actor: Actor,
    ) -> Page[ChassisRead]:
        del actor
        items, total = await self._repo.list_for_olt(
            olt_id,
            offset=params.offset,
            limit=params.limit,
        )
        return Page[ChassisRead](
            items=[ChassisRead.model_validate(c) for c in items],
            total=total,
            page=params.page,
            size=params.size,
        )

    async def create(self, payload: ChassisCreate, *, actor: Actor) -> ChassisRead:
        # olt_id precisa existir e estar viva.
        olt_repo = OltRepository(self._session)
        olt = await olt_repo.get_by_id(payload.olt_id)
        if olt is None:
            raise OltReferenceInvalid(payload.olt_id)

        # Pré-check de unicidade (olt_id, chassis_index).
        existing = await self._repo.get_by_olt_and_index(payload.olt_id, payload.chassis_index)
        if existing is not None:
            raise ChassisConflict(payload.olt_id, payload.chassis_index)

        chassis = Chassis(
            olt_id=payload.olt_id,
            chassis_index=payload.chassis_index,
            description=payload.description,
        )
        try:
            await self._repo.add(chassis)
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ChassisConflict(payload.olt_id, payload.chassis_index) from exc

        log.info(
            "chassis.created",
            chassis_id=str(chassis.chassis_id),
            olt_id=str(chassis.olt_id),
            chassis_index=chassis.chassis_index,
            actor=str(actor),
        )
        return ChassisRead.model_validate(chassis)

    async def update(
        self,
        chassis_id: UUID,
        payload: ChassisUpdate,
        *,
        actor: Actor,
    ) -> ChassisRead:
        chassis = await self._repo.get_by_id(chassis_id)
        if chassis is None:
            raise ChassisNotFound(chassis_id)

        data = payload.model_dump(exclude_unset=True)
        if not data:
            return ChassisRead.model_validate(chassis)

        if "description" in data:
            chassis.description = data["description"]

        await self._session.commit()
        await self._session.refresh(chassis)

        log.info(
            "chassis.updated",
            chassis_id=str(chassis.chassis_id),
            fields=list(data.keys()),
            actor=str(actor),
        )
        return ChassisRead.model_validate(chassis)
