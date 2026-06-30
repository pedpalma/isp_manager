# Service de provisioning_template.

# Validações no create:
# 1. manufacturer existe e está ativo
# 2. olt_model (se informado) existe E pertence ao manufacturer
# 3. raw_template.scope == template_scope da coluna
# 4. Unicidade (manufacturer, olt_model, name, version) pré-check via repo
# 5. IntegrityError fallback

# Update: campos da chave única são imutáveis (não estão no UpdateSchema),
# portanto NÃO precisa de try/except IntegrityError. Padrão update_no_try_except.

# created_by_user_id: recebido como parâmetro de create(); vem do CurrentUser
# na rota. None quando o caller não consegue ser identificado.

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.exceptions import NotFoundError
from app.domains.inventory.models.manufacturer import Manufacturer
from app.domains.inventory.models.olt_model import OltModel
from app.domains.provisioning.exceptions import (
    ManufacturerOltModelMismatch,
    ManufacturerReferenceInvalid,
    OltModelReferenceInvalid,
    ProvisioningTemplateConflict,
    ProvisioningTemplateNotFound,
    TemplateScopeMismatch,
)
from app.domains.provisioning.models.provisioning_template import ProvisioningTemplate
from app.domains.provisioning.repositories.provisioning_template import (
    ProvisioningTemplateRepository,
)
from app.domains.provisioning.schemas.provisioning_template import (
    ProvisioningTemplateCreate,
    ProvisioningTemplateRead,
    ProvisioningTemplateUpdate,
)

log = structlog.get_logger(__name__)


class ProvisioningTemplateService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = ProvisioningTemplateRepository(session)

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
        payload: ProvisioningTemplateCreate,
        *,
        actor: Actor,
        created_by_user_id: UUID | None,
    ) -> ProvisioningTemplateRead:
        await self._validate_manufacturer(payload.manufacturer_id)
        if payload.olt_model_id is not None:
            await self._validate_olt_model_for_manufacturer(
                manufacturer_id=payload.manufacturer_id,
                olt_model_id=payload.olt_model_id,
            )
        # Coerência scope (coluna) <-> raw_template.scope (JSONB).
        if payload.raw_template.scope.value != payload.template_scope.value:
            raise TemplateScopeMismatch(
                payload.template_scope.value, payload.raw_template.scope.value
            )

        # Pré-check de unicidade.
        existing = await self._repo.get_by_key(
            manufacturer_id=payload.manufacturer_id,
            olt_model_id=payload.olt_model_id,
            name=payload.name,
            version=payload.version,
        )
        if existing is not None:
            raise ProvisioningTemplateConflict(
                payload.manufacturer_id,
                payload.olt_model_id,
                payload.name,
                payload.version,
            )

        obj = ProvisioningTemplate(
            manufacturer_id=payload.manufacturer_id,
            olt_model_id=payload.olt_model_id,
            created_by_user_id=created_by_user_id,
            template_scope=payload.template_scope.value,
            name=payload.name,
            version=payload.version,
            firmware_constraint=payload.firmware_constraint,
            command_vars=payload.command_vars,
            raw_template=payload.raw_template.model_dump(mode="json"),
            active=payload.active,
        )
        try:
            await self._repo.add(obj)
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            # Race entre o SELECT pré-check e o INSERT: o índice TOTAL pegou.
            raise ProvisioningTemplateConflict(
                payload.manufacturer_id,
                payload.olt_model_id,
                payload.name,
                payload.version,
            ) from exc

        await self._session.refresh(obj)
        log.info(
            "provisioning_template.created",
            provisioning_template_id=str(obj.provisioning_template_id),
            manufacturer_id=str(obj.manufacturer_id),
            olt_model_id=str(obj.olt_model_id) if obj.olt_model_id else None,
            name=obj.name,
            version=obj.version,
            actor=str(actor),
        )
        return ProvisioningTemplateRead.model_validate(obj)

    async def get(self, provisioning_template_id: UUID) -> ProvisioningTemplateRead:
        obj = await self._repo.get_by_id(provisioning_template_id)
        if obj is None:
            raise ProvisioningTemplateNotFound(provisioning_template_id)
        return ProvisioningTemplateRead.model_validate(obj)

    async def list_page(
        self,
        *,
        offset: int,
        limit: int,
        manufacturer_id: UUID | None = None,
        olt_model_id: UUID | None = None,
        template_scope: str | None = None,
        active: bool | None = None,
    ) -> tuple[list[ProvisioningTemplateRead], int]:
        items, total = await self._repo.list_page(
            offset=offset,
            limit=limit,
            manufacturer_id=manufacturer_id,
            olt_model_id=olt_model_id,
            template_scope=template_scope,
            active=active,
        )
        return [ProvisioningTemplateRead.model_validate(i) for i in items], total

    async def update(
        self,
        provisioning_template_id: UUID,
        payload: ProvisioningTemplateUpdate,
        *,
        actor: Actor,
    ) -> ProvisioningTemplateRead:
        obj = await self._repo.get_by_id(provisioning_template_id)
        if obj is None:
            raise ProvisioningTemplateNotFound(provisioning_template_id)

        data = payload.model_dump(exclude_unset=True)
        if not data:
            return ProvisioningTemplateRead.model_validate(obj)

        # raw_template chega como RawTemplate quando enviado.
        # model_dump(exclude_unset) já o entrega como dict aninhado;
        # preservamos sem coerce extra.
        if "raw_template" in data and data["raw_template"] is not None:
            # Coerência scope: como template_scope é IMUTÁVEL,
            # se raw_template novo for enviado, scope dele tem que
            # bater com o template_scope persistido.
            new_scope = data["raw_template"].get("scope")
            if new_scope is not None and new_scope != obj.template_scope:
                raise TemplateScopeMismatch(obj.template_scope, str(new_scope))

        for field, value in data.items():
            setattr(obj, field, value)
        await self._session.commit()
        await self._session.refresh(obj)
        log.info(
            "provisioning_template.updated",
            provisioning_template_id=str(obj.provisioning_template_id),
            fields=list(data.keys()),
            actor=str(actor),
        )
        return ProvisioningTemplateRead.model_validate(obj)

    @staticmethod
    def raise_not_found(provisioning_template_id: UUID) -> NotFoundError:
        return ProvisioningTemplateNotFound(provisioning_template_id)
