# Repository de ProvisioningTemplate.

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.provisioning.models.provisioning_template import ProvisioningTemplate


class ProvisioningTemplateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, provisioning_template_id: UUID) -> ProvisioningTemplate | None:
        stmt = select(ProvisioningTemplate).where(
            ProvisioningTemplate.provisioning_template_id == provisioning_template_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_key(
        self,
        *,
        manufacturer_id: UUID,
        olt_model_id: UUID | None,
        name: str,
        version: str,
    ) -> ProvisioningTemplate | None:
        """Pré-check de unicidade da chave."""
        stmt = select(ProvisioningTemplate).where(
            ProvisioningTemplate.manufacturer_id == manufacturer_id,
            ProvisioningTemplate.name == name,
            ProvisioningTemplate.version == version,
        )
        if olt_model_id is None:
            stmt = stmt.where(ProvisioningTemplate.olt_model_id.is_(None))
        else:
            stmt = stmt.where(ProvisioningTemplate.olt_model_id == olt_model_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_page(
        self,
        *,
        offset: int,
        limit: int,
        manufacturer_id: UUID | None = None,
        olt_model_id: UUID | None = None,
        template_scope: str | None = None,
        active: bool | None = None,
    ) -> tuple[Sequence[ProvisioningTemplate], int]:
        """Listagem paginada com filtros opcionais."""
        base = select(ProvisioningTemplate)
        count_query = select(func.count()).select_from(ProvisioningTemplate)

        if manufacturer_id is not None:
            base = base.where(ProvisioningTemplate.manufacturer_id == manufacturer_id)
            count_query = count_query.where(
                ProvisioningTemplate.manufacturer_id == manufacturer_id,
            )
        if olt_model_id is not None:
            base = base.where(ProvisioningTemplate.olt_model_id == olt_model_id)
            count_query = count_query.where(
                ProvisioningTemplate.olt_model_id == olt_model_id,
            )
        if template_scope is not None:
            base = base.where(ProvisioningTemplate.template_scope == template_scope)
            count_query = count_query.where(
                ProvisioningTemplate.template_scope == template_scope,
            )
        if active is not None:
            base = base.where(ProvisioningTemplate.active.is_(active))
            count_query = count_query.where(ProvisioningTemplate.active.is_(active))

        page_query = (
            base.order_by(
                ProvisioningTemplate.name.asc(),
                ProvisioningTemplate.version.asc(),
            )
            .offset(offset)
            .limit(limit)
        )
        items_result = await self._session.execute(page_query)
        items: Sequence[ProvisioningTemplate] = items_result.scalars().all()

        total_result = await self._session.execute(count_query)
        total: int = total_result.scalar_one()

        return items, total

    async def add(self, obj: ProvisioningTemplate) -> None:
        self._session.add(obj)
        await self._session.flush()

    async def flush(self) -> None:
        await self._session.flush()
