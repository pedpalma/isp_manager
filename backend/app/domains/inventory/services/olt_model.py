# Service do OltModel.

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.logging import get_logger
from app.domains.inventory.exceptions import (
    ManufacturerNotFound,
    OltModelConflict,
    OltModelNotFound,
)
from app.domains.inventory.models.olt_model import OltModel
from app.domains.inventory.repositories.manufacturer import ManufacturerRepository
from app.domains.inventory.repositories.olt_model import OltModelRepository
from app.domains.inventory.schemas.olt_model import OltModelCreate, OltModelUpdate

log = get_logger(__name__)


class OltModelService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = OltModelRepository(session)
        # ManufacturerRepository é leitura aqui: usado só para validar FK.
        self._manufacturer_repo = ManufacturerRepository(session)

    async def get(self, olt_model_id: UUID, *, actor: Actor) -> OltModel:
        del actor
        m = await self._repo.get_by_id(olt_model_id)
        if m is None:
            raise OltModelNotFound(olt_model_id)
        return m

    async def list_page(
        self,
        *,
        offset: int,
        limit: int,
        only_active: bool = False,
        manufacturer_id: UUID | None = None,
        search: str | None = None,
        actor: Actor,
    ) -> tuple[Sequence[OltModel], int]:
        del actor
        return await self._repo.list_page(
            offset=offset,
            limit=limit,
            only_active=only_active,
            manufacturer_id=manufacturer_id,
            search=search,
        )

    async def create(self, data: OltModelCreate, *, actor: Actor) -> OltModel:
        # Valida FK antes do INSERT para mensagem clara. Sem isto, um
        # manufacturer_id inválido viraria IntegrityError genérico.
        manufacturer = await self._manufacturer_repo.get_by_id(data.manufacturer_id)
        if manufacturer is None:
            raise ManufacturerNotFound(data.manufacturer_id)

        existing = await self._repo.get_by_manufacturer_and_model(data.manufacturer_id, data.model)
        if existing is not None:
            raise OltModelConflict(data.manufacturer_id, data.model)

        m = OltModel(
            manufacturer_id=data.manufacturer_id,
            model=data.model,
            active=data.active,
        )
        try:
            await self._repo.add(m)
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise OltModelConflict(data.manufacturer_id, data.model) from exc

        log.info(
            "olt_model.created",
            olt_model_id=str(m.olt_model_id),
            manufacturer_id=str(m.manufacturer_id),
            model=m.model,
            actor=actor.username,
        )
        return m

    async def update(
        self,
        olt_model_id: UUID,
        data: OltModelUpdate,
        *,
        actor: Actor,
    ) -> OltModel:
        m = await self._repo.get_by_id(olt_model_id)
        if m is None:
            raise OltModelNotFound(olt_model_id)

        payload = data.model_dump(exclude_unset=True)

        if "model" in payload and payload["model"] != m.model:
            existing = await self._repo.get_by_manufacturer_and_model(
                m.manufacturer_id, payload["model"]
            )
            if existing is not None:
                raise OltModelConflict(m.manufacturer_id, payload["model"])

        for field, value in payload.items():
            setattr(m, field, value)

        try:
            await self._repo.flush()
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise OltModelConflict(m.manufacturer_id, m.model) from exc

        log.info(
            "olt_model.updated",
            olt_model_id=str(m.olt_model_id),
            fields=list(payload.keys()),
            actor=actor.username,
        )
        return m
