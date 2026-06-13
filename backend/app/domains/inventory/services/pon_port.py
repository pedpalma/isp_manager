# Service da PonPort.

from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.logging import get_logger
from app.core.pagination import Page, PageParams
from app.domains.inventory.enums import ADMIN_MUTABLE_PORT_STATUS, PortStatus
from app.domains.inventory.exceptions import (
    PonPortConflict,
    PonPortNotFound,
    PonPortStatusInvalid,
    SlotReferenceInvalid,
)
from app.domains.inventory.models.pon_port import PonPort
from app.domains.inventory.repositories.pon_port import PonPortRepository
from app.domains.inventory.repositories.slot import SlotRepository
from app.domains.inventory.schemas.pon_port import (
    PonPortCreate,
    PonPortRead,
    PonPortUpdate,
)

log = get_logger(__name__)


def _ensure_admin_mutable_status(value: PortStatus) -> None:
    if value not in ADMIN_MUTABLE_PORT_STATUS:
        raise PonPortStatusInvalid(
            requested=value.value,
            allowed=sorted(v.value for v in ADMIN_MUTABLE_PORT_STATUS),
        )


class PonPortService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = PonPortRepository(session)

    async def get(self, pon_port_id: UUID, *, actor: Actor) -> PonPortRead:
        del actor
        pon = await self._repo.get_by_id(pon_port_id)
        if pon is None:
            raise PonPortNotFound(pon_port_id)
        return PonPortRead.model_validate(pon)

    async def list_for_slot(
        self,
        slot_id: UUID,
        params: PageParams,
        *,
        actor: Actor,
    ) -> Page[PonPortRead]:
        del actor
        items, total = await self._repo.list_for_slot(
            slot_id,
            offset=params.offset,
            limit=params.limit,
        )
        return Page[PonPortRead](
            items=[PonPortRead.model_validate(p) for p in items],
            total=total,
            page=params.page,
            size=params.size,
        )

    async def create(self, payload: PonPortCreate, *, actor: Actor) -> PonPortRead:
        slot_repo = SlotRepository(self._session)
        slot = await slot_repo.get_by_id(payload.slot_id)
        if slot is None:
            raise SlotReferenceInvalid(payload.slot_id)

        existing = await self._repo.get_by_slot_and_index(payload.slot_id, payload.pon_index)
        if existing is not None:
            raise PonPortConflict(payload.slot_id, payload.pon_index)

        pon = PonPort(
            slot_id=payload.slot_id,
            pon_index=payload.pon_index,
            pon_type=payload.pon_type,
        )
        try:
            await self._repo.add(pon)
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise PonPortConflict(payload.slot_id, payload.pon_index) from exc

        log.info(
            "pon_port.created",
            pon_port_id=str(pon.pon_port_id),
            slot_id=str(pon.slot_id),
            pon_index=pon.pon_index,
            pon_type=pon.pon_type.value,
            actor=str(actor),
        )
        return PonPortRead.model_validate(pon)

    async def update(
        self,
        pon_port_id: UUID,
        payload: PonPortUpdate,
        *,
        actor: Actor,
    ) -> PonPortRead:
        pon = await self._repo.get_by_id(pon_port_id)
        if pon is None:
            raise PonPortNotFound(pon_port_id)

        data = payload.model_dump(exclude_unset=True)
        if not data:
            return PonPortRead.model_validate(pon)

        if "status" in data and data["status"] is not None:
            _ensure_admin_mutable_status(data["status"])
            pon.status = data["status"]

        if "pon_type" in data and data["pon_type"] is not None:
            pon.pon_type = data["pon_type"]

        await self._session.commit()
        await self._session.refresh(pon)

        log.info(
            "pon_port.updated",
            pon_port_id=str(pon.pon_port_id),
            fields=list(data.keys()),
            actor=str(actor),
        )
        return PonPortRead.model_validate(pon)
