# Service da VLAN.

from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.logging import get_logger
from app.core.pagination import Page, PageParams
from app.domains.inventory.exceptions import (
    OltReferenceInvalid,
    VlanConflict,
    VlanNotFound,
)
from app.domains.inventory.models.vlan import Vlan
from app.domains.inventory.repositories.olt import OltRepository
from app.domains.inventory.repositories.vlan import VlanRepository
from app.domains.inventory.schemas.vlan import VlanCreate, VlanRead, VlanUpdate

log = get_logger(__name__)


class VlanService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = VlanRepository(session)

    async def get(self, vlan_id: UUID, *, actor: Actor) -> VlanRead:
        del actor
        vlan = await self._repo.get_by_id(vlan_id)
        if vlan is None:
            raise VlanNotFound(vlan_id)
        return VlanRead.model_validate(vlan)

    async def list_for_olt(
        self, olt_id: UUID, params: PageParams, *, actor: Actor
    ) -> Page[VlanRead]:
        del actor
        items, total = await self._repo.list_for_olt(
            olt_id, offset=params.offset, limit=params.limit
        )
        return Page[VlanRead](
            items=[VlanRead.model_validate(v) for v in items],
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    async def create(self, payload: VlanCreate, *, actor: Actor) -> VlanRead:
        # olt_id precisa existir e estar viva.
        olt_repo = OltRepository(self._session)
        olt = await olt_repo.get_by_id(payload.olt_id)
        if olt is None:
            raise OltReferenceInvalid(payload.olt_id)

        # Pre-check de unicidade (olt_id, vlan_number) TOTAL.
        existing = await self._repo.get_by_olt_and_number(payload.olt_id, payload.vlan_number)
        if existing is not None:
            raise VlanConflict(payload.olt_id, payload.vlan_number)

        vlan = Vlan(
            olt_id=payload.olt_id,
            vlan_number=payload.vlan_number,
            name=payload.name,
            type=payload.type,
            description=payload.description,
            active=payload.active,
        )
        try:
            await self._repo.add(vlan)
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise VlanConflict(payload.olt_id, payload.vlan_number) from exc

        log.info(
            "vlan.created",
            vlan_id=str(vlan.vlan_id),
            olt_id=str(vlan.olt_id),
            vlan_number=vlan.vlan_number,
            actor=str(actor),
        )
        return VlanRead.model_validate(vlan)

    async def update(self, vlan_id: UUID, payload: VlanUpdate, *, actor: Actor) -> VlanRead:
        vlan = await self._repo.get_by_id(vlan_id)
        if vlan is None:
            raise VlanNotFound(vlan_id)

        data = payload.model_dump(exclude_unset=True)
        if not data:
            return VlanRead.model_validate(vlan)

        # Nenhum campo mutável afeta a unicidade (olt_id/vlan_number imutáveis).
        for field, value in data.items():
            setattr(vlan, field, value)

        await self._session.commit()
        await self._session.refresh(vlan)

        log.info(
            "vlan.updated",
            vlan_id=str(vlan.vlan_id),
            fields=list(data.keys()),
            actor=str(actor),
        )
        return VlanRead.model_validate(vlan)
