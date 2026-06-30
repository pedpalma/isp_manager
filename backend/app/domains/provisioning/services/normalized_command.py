# Service de normalized_command.
#
# Validações no create:
# 1. manufacturer existe e está ativo
# 2. olt_model (se informado) existe E pertence ao manufacturer
# 3. Unicidade PARCIAL (active=TRUE) — pré-check via repo
# 4. IntegrityError fallback (race entre pré-check e INSERT)


from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.domains.inventory.models.manufacturer import Manufacturer
from app.domains.inventory.models.olt_model import OltModel
from app.domains.provisioning.exceptions import (
    ManufacturerOltModelMismatch,
    ManufacturerReferenceInvalid,
    NormalizedCommandConflict,
    NormalizedCommandNotFound,
    OltModelReferenceInvalid,
)
from app.domains.provisioning.models.normalized_command import NormalizedCommand
from app.domains.provisioning.repositories.normalized_command import (
    NormalizedCommandRepository,
)
from app.domains.provisioning.schemas.normalized_command import (
    NormalizedCommandCreate,
    NormalizedCommandRead,
    NormalizedCommandUpdate,
)

log = structlog.get_logger(__name__)


class NormalizedCommandService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = NormalizedCommandRepository(session)

    async def _validate_manufacturer(self, manufacturer_id: UUID) -> None:
        stmt = select(Manufacturer.manufacturer_id).where(
            Manufacturer.manufacturer_id == manufacturer_id,
            Manufacturer.active.is_(True),
        )
        if (await self._session.execute(stmt)).scalar_one_or_none() is None:
            raise ManufacturerReferenceInvalid(manufacturer_id)

    async def _validate_olt_model_for_manufacturer(
        self, *, manufacturer_id: UUID, olt_model_id: UUID
    ) -> None:
        stmt = select(OltModel.manufacturer_id).where(
            OltModel.olt_model_id == olt_model_id,
            OltModel.active.is_(True),
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise OltModelReferenceInvalid(olt_model_id)
        if row != manufacturer_id:
            raise ManufacturerOltModelMismatch(manufacturer_id, olt_model_id)

    async def create(
        self,
        payload: NormalizedCommandCreate,
        *,
        actor: Actor,
    ) -> NormalizedCommandRead:
        await self._validate_manufacturer(payload.manufacturer_id)
        if payload.olt_model_id is not None:
            await self._validate_olt_model_for_manufacturer(
                manufacturer_id=payload.manufacturer_id,
                olt_model_id=payload.olt_model_id,
            )

        # Pré-check só vale se active=TRUE (índice parcial).
        if payload.active:
            existing = await self._repo.get_active_by_key(
                manufacturer_id=payload.manufacturer_id,
                olt_model_id=payload.olt_model_id,
                command_key=payload.command_key,
                version_constraint=payload.version_constraint,
            )
            if existing is not None:
                raise NormalizedCommandConflict(
                    payload.manufacturer_id,
                    payload.olt_model_id,
                    payload.command_key,
                    payload.version_constraint,
                )

        obj = NormalizedCommand(
            manufacturer_id=payload.manufacturer_id,
            olt_model_id=payload.olt_model_id,
            command_key=payload.command_key,
            command_type=payload.command_type.value,
            template_string=payload.template_string,
            output_parser=payload.output_parser,
            version_constraint=payload.version_constraint,
            timeout_ms=payload.timeout_ms,
            requires_privileged=payload.requires_privileged,
            supports_ssh=payload.supports_ssh,
            supports_telnet=payload.supports_telnet,
            active=payload.active,
        )
        try:
            await self._repo.add(obj)
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            # Aqui usamos payload.* (Pydantic) e NÃO obj.* (ORM expirado);
            # safe porque payload não passa por expiração de sessão.
            raise NormalizedCommandConflict(
                payload.manufacturer_id,
                payload.olt_model_id,
                payload.command_key,
                payload.version_constraint,
            ) from exc

        await self._session.refresh(obj)
        log.info(
            "normalized_command.created",
            normalized_command_id=str(obj.normalized_command_id),
            manufacturer_id=str(obj.manufacturer_id),
            olt_model_id=str(obj.olt_model_id) if obj.olt_model_id else None,
            command_key=obj.command_key,
            actor=str(actor),
        )
        return NormalizedCommandRead.model_validate(obj)

    async def get(self, normalized_command_id: UUID) -> NormalizedCommandRead:
        obj = await self._repo.get_by_id(normalized_command_id)
        if obj is None:
            raise NormalizedCommandNotFound(normalized_command_id)
        return NormalizedCommandRead.model_validate(obj)

    async def list_page(
        self,
        *,
        offset: int,
        limit: int,
        manufacturer_id: UUID | None = None,
        olt_model_id: UUID | None = None,
        command_key: str | None = None,
        command_type: str | None = None,
        active: bool | None = None,
    ) -> tuple[list[NormalizedCommandRead], int]:
        items, total = await self._repo.list_page(
            offset=offset,
            limit=limit,
            manufacturer_id=manufacturer_id,
            olt_model_id=olt_model_id,
            command_key=command_key,
            command_type=command_type,
            active=active,
        )
        return [NormalizedCommandRead.model_validate(i) for i in items], total

    async def update(
        self,
        normalized_command_id: UUID,
        payload: NormalizedCommandUpdate,
        *,
        actor: Actor,
    ) -> NormalizedCommandRead:
        obj = await self._repo.get_by_id(normalized_command_id)
        if obj is None:
            raise NormalizedCommandNotFound(normalized_command_id)

        data = payload.model_dump(exclude_unset=True)
        if not data:
            return NormalizedCommandRead.model_validate(obj)

        # Aplicar values em memória para detectar reativação que colide.
        for field, value in data.items():
            if field == "command_type" and value is not None:
                # Enum -> str (coluna é TEXT).
                setattr(obj, field, value.value if hasattr(value, "value") else value)
            else:
                setattr(obj, field, value)

        # Snapshot dos campos da chave ANTES do commit. Necessário porque
        # session.rollback() expira os atributos do ORM e ler obj.* depois
        # dispara lazy-load assíncrono (MissingGreenlet em pytest-asyncio).
        key_manufacturer_id = obj.manufacturer_id
        key_olt_model_id = obj.olt_model_id
        key_command_key = obj.command_key
        key_version_constraint = obj.version_constraint

        try:
            await self._session.commit()
        except IntegrityError as exc:
            # Reativação (active False -> True) que colide com outro ativo
            # de mesma chave. Único caminho de conflito no Update aqui.
            await self._session.rollback()
            raise NormalizedCommandConflict(
                key_manufacturer_id,
                key_olt_model_id,
                key_command_key,
                key_version_constraint,
            ) from exc

        await self._session.refresh(obj)
        log.info(
            "normalized_command.updated",
            normalized_command_id=str(obj.normalized_command_id),
            fields=list(data.keys()),
            actor=str(actor),
        )
        return NormalizedCommandRead.model_validate(obj)
