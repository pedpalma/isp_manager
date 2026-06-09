# Service do Manufacturer e regras de negócio.
# Responsabilidades:
# - Validar invariantes do domínio (slug único, etc.).
# - Traduzir IntegrityError em erros de domínio.
# - Controlar os limites da transação: COMMIT em sucesso, ROLLBACK em falha. O repository não faz commit nunca.
# - Logar eventos de negócio (manufacturer.created, .updated, .deactivated).
# O service não sabe nada sobre HTTP. Quem traduz a exceção para resposta HTTP é o handler global em app/api/errors.py.

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.logging import get_logger
from app.domains.inventory.exceptions import (
    ManufacturerNotFound,
    ManufacturerSlugConflict,
)
from app.domains.inventory.models.manufacturer import Manufacturer
from app.domains.inventory.repositories.manufacturer import ManufacturerRepository
from app.domains.inventory.schemas.manufacturer import (
    ManufacturerCreate,
    ManufacturerUpdate,
)

log = get_logger(__name__)


class ManufacturerService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = ManufacturerRepository(session)

    # Leitura
    async def get(self, manufacturer_id: UUID, *, actor: Actor) -> Manufacturer:
        del actor
        m = await self._repo.get_by_id(manufacturer_id)
        if m is None:
            raise ManufacturerNotFound(manufacturer_id)
        return m

    async def list_page(
        self,
        *,
        offset: int,
        limit: int,
        only_active: bool = False,
        search: str | None = None,
        actor: Actor,
    ) -> tuple[Sequence[Manufacturer], int]:
        del actor
        return await self._repo.list_page(
            offset=offset,
            limit=limit,
            only_active=only_active,
            search=search,
        )

    # Escrita
    async def create(self, data: ManufacturerCreate, *, actor: Actor) -> Manufacturer:
        # Pré-check: dá uma mensagem nítida no caso normal (slug duplicado).
        existing = await self._repo.get_by_slug(data.slug)
        if existing is not None:
            raise ManufacturerSlugConflict(data.slug)

        m = Manufacturer(name=data.name, slug=data.slug, active=data.active)
        try:
            await self._repo.add(m)
            await self._session.commit()
        except IntegrityError as exc:
            # Cobre a corrida: pré-check passou, mas outro request inseriu
            # o mesmo slug entre o SELECT e o INSERT.
            await self._session.rollback()
            raise ManufacturerSlugConflict(data.slug) from exc

        log.info(
            "manufacturer.created",
            manufacturer_id=str(m.manufacturer_id),
            slug=m.slug,
            actor=actor.username,
        )
        return m

    async def update(
        self,
        manufacturer_id: UUID,
        data: ManufacturerUpdate,
        *,
        actor: Actor,
    ) -> Manufacturer:
        m = await self._repo.get_by_id(manufacturer_id)
        if m is None:
            raise ManufacturerNotFound(manufacturer_id)
        # `model_dump(exclude_unset=True)`: pega só os campos que vieram no corpo do PATCH.
        payload = data.model_dump(exclude_unset=True)

        if "slug" in payload and payload["slug"] != m.slug:
            existing = await self._repo.get_by_slug(payload["slug"])
            if existing is not None:
                raise ManufacturerSlugConflict(payload["slug"])

        for field, value in payload.items():
            setattr(m, field, value)

        try:
            await self._repo.flush()
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            # Se ainda assim o IntegrityError veio, é quase certo conflito de slug.
            raise ManufacturerSlugConflict(payload.get("slug", m.slug)) from exc

        log.info(
            "manufacturer.updated",
            manufacturer_id=str(m.manufacturer_id),
            fields=list(payload.keys()),
            actor=actor.username,
        )
        return m
