# Service do Slot.

from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.logging import get_logger
from app.core.pagination import Page, PageParams
from app.domains.inventory.enums import ADMIN_MUTABLE_PORT_STATUS, PortStatus
from app.domains.inventory.exceptions import (
    ChassisReferenceInvalid,
    SlotConflict,
    SlotNotFound,
    SlotStatusInvalid,
)
from app.domains.inventory.models.slot import Slot
from app.domains.inventory.repositories.chassis import ChassisRepository
from app.domains.inventory.repositories.slot import SlotRepository
from app.domains.inventory.schemas.slot import SlotCreate, SlotRead, SlotUpdate

log = get_logger(__name__)


def _ensure_admin_mutable_status(value: PortStatus) -> None:
    """Aplicação só seta 'disabled' e 'unknown'. Demais valores são da Coleta."""
    if value not in ADMIN_MUTABLE_PORT_STATUS:
        raise SlotStatusInvalid(
            requested=value.value,
            allowed=sorted(v.value for v in ADMIN_MUTABLE_PORT_STATUS),
        )


class SlotService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = SlotRepository(session)

    async def get(self, slot_id: UUID, *, actor: Actor) -> SlotRead:
        del actor
        slot = await self._repo.get_by_id(slot_id)
        if slot is None:
            raise SlotNotFound(slot_id)
        return SlotRead.model_validate(slot)

    async def list_for_chassis(
        self,
        chassis_id: UUID,
        params: PageParams,
        *,
        actor: Actor,
    ) -> Page[SlotRead]:
        del actor
        items, total = await self._repo.list_for_chassis(
            chassis_id,
            offset=params.offset,
            limit=params.limit,
        )
        return Page[SlotRead](
            items=[SlotRead.model_validate(s) for s in items],
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    async def create(self, payload: SlotCreate, *, actor: Actor) -> SlotRead:
        # Cascateado: chassis precisa existir e ter OLT pai viva.
        chassis_repo = ChassisRepository(self._session)
        chassis = await chassis_repo.get_by_id(payload.chassis_id)
        if chassis is None:
            raise ChassisReferenceInvalid(payload.chassis_id)

        existing = await self._repo.get_by_chassis_and_index(payload.chassis_id, payload.slot_index)
        if existing is not None:
            raise SlotConflict(payload.chassis_id, payload.slot_index)

        slot = Slot(
            chassis_id=payload.chassis_id,
            slot_index=payload.slot_index,
            board_type=payload.board_type,
        )
        try:
            await self._repo.add(slot)
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise SlotConflict(payload.chassis_id, payload.slot_index) from exc

        log.info(
            "slot.created",
            slot_id=str(slot.slot_id),
            chassis_id=str(slot.chassis_id),
            slot_index=slot.slot_index,
            actor=str(actor),
        )
        return SlotRead.model_validate(slot)

    async def update(
        self,
        slot_id: UUID,
        payload: SlotUpdate,
        *,
        actor: Actor,
    ) -> SlotRead:
        slot = await self._repo.get_by_id(slot_id)
        if slot is None:
            raise SlotNotFound(slot_id)

        data = payload.model_dump(exclude_unset=True)
        if not data:
            return SlotRead.model_validate(slot)

        if "status" in data and data["status"] is not None:
            _ensure_admin_mutable_status(data["status"])
            slot.status = data["status"]

        if "board_type" in data:
            slot.board_type = data["board_type"]

        await self._session.commit()
        await self._session.refresh(slot)

        log.info(
            "slot.updated",
            slot_id=str(slot.slot_id),
            fields=list(data.keys()),
            actor=str(actor),
        )
        return SlotRead.model_validate(slot)
