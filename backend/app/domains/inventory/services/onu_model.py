# Service do OnuModel e regras de negócio.
# Particularidade em relação ao OltModel: o `vendor_id` tem unicidade PARCIAL no banco (UNIQUE WHERE vendor_id IS NOT NULL).
# É preciso validar isso explicitamente, porque o ORM não consegue ler a constraint parcial.

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.logging import get_logger
from app.domains.inventory.exceptions import (
    ManufacturerNotFound,
    OnuModelConflict,
    OnuModelNotFound,
    OnuModelVendorIdConflict,
)
from app.domains.inventory.models.onu_model import OnuModel
from app.domains.inventory.repositories.manufacturer import ManufacturerRepository
from app.domains.inventory.repositories.onu_model import OnuModelRepository
from app.domains.inventory.schemas.onu_model import OnuModelCreate, OnuModelUpdate

log = get_logger(__name__)


class OnuModelService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = OnuModelRepository(session)
        self._manufacturer_repo = ManufacturerRepository(session)

    async def get(self, onu_model_id: UUID, *, actor: Actor) -> OnuModel:
        del actor
        m = await self._repo.get_by_id(onu_model_id)
        if m is None:
            raise OnuModelNotFound(onu_model_id)
        return m

    async def list_page(
        self,
        *,
        offset: int,
        limit: int,
        only_active: bool = False,
        manufacturer_id: UUID | None = None,
        category: str | None = None,
        search: str | None = None,
        actor: Actor,
    ) -> tuple[Sequence[OnuModel], int]:
        del actor
        return await self._repo.list_page(
            offset=offset,
            limit=limit,
            only_active=only_active,
            manufacturer_id=manufacturer_id,
            category=category,
            search=search,
        )

    async def create(self, data: OnuModelCreate, *, actor: Actor) -> OnuModel:
        manufacturer = await self._manufacturer_repo.get_by_id(data.manufacturer_id)
        if manufacturer is None:
            raise ManufacturerNotFound(data.manufacturer_id)

        existing = await self._repo.get_by_manufacturer_and_model(data.manufacturer_id, data.model)
        if existing is not None:
            raise OnuModelConflict(data.manufacturer_id, data.model)

        # Unicidade parcial: só checa se o vendor_id foi informado.
        if data.vendor_id is not None:
            by_vendor = await self._repo.get_by_manufacturer_and_vendor_id(
                data.manufacturer_id, data.vendor_id
            )
            if by_vendor is not None:
                raise OnuModelVendorIdConflict(data.manufacturer_id, data.vendor_id)

        m = OnuModel(
            manufacturer_id=data.manufacturer_id,
            model=data.model,
            vendor_id=data.vendor_id,
            category=data.category,
            capabilities_json=data.capabilities_json,
            active=data.active,
        )
        try:
            await self._repo.add(m)
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise OnuModelConflict(data.manufacturer_id, data.model) from exc

        log.info(
            "onu_model.created",
            onu_model_id=str(m.onu_model_id),
            manufacturer_id=str(m.manufacturer_id),
            model=m.model,
            vendor_id=m.vendor_id,
            actor=actor.username,
        )
        return m

    async def update(
        self,
        onu_model_id: UUID,
        data: OnuModelUpdate,
        *,
        actor: Actor,
    ) -> OnuModel:
        m = await self._repo.get_by_id(onu_model_id)
        if m is None:
            raise OnuModelNotFound(onu_model_id)

        payload = data.model_dump(exclude_unset=True)

        if "model" in payload and payload["model"] != m.model:
            existing = await self._repo.get_by_manufacturer_and_model(
                m.manufacturer_id, payload["model"]
            )
            if existing is not None:
                raise OnuModelConflict(m.manufacturer_id, payload["model"])

        if (
            "vendor_id" in payload
            and payload["vendor_id"] is not None
            and payload["vendor_id"] != m.vendor_id
        ):
            by_vendor = await self._repo.get_by_manufacturer_and_vendor_id(
                m.manufacturer_id, payload["vendor_id"]
            )
            if by_vendor is not None:
                raise OnuModelVendorIdConflict(m.manufacturer_id, payload["vendor_id"])

        for field, value in payload.items():
            setattr(m, field, value)

        try:
            await self._repo.flush()
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise OnuModelConflict(m.manufacturer_id, m.model) from exc

        log.info(
            "onu_model.updated",
            onu_model_id=str(m.onu_model_id),
            fields=list(payload.keys()),
            actor=actor.username,
        )
        return m
