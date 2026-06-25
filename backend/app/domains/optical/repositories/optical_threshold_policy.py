# Repository de OpticalThresholdPolicy.

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.optical.enums import OpticalScopeType
from app.domains.optical.models.optical_threshold_policy import (
    OpticalThresholdPolicy,
)


class OpticalThresholdPolicyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, policy_id: UUID) -> OpticalThresholdPolicy | None:
        stmt = select(OpticalThresholdPolicy).where(
            OpticalThresholdPolicy.optical_threshold_policy_id == policy_id
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_by_scope_and_metric(
        self,
        *,
        scope_type: OpticalScopeType,
        scope_id: UUID | None,
        metric_name: str,
    ) -> OpticalThresholdPolicy | None:
        """Pre-check para uq_optical_threshold_policy_scope.
        scope_id NULL = escopo global, comparado com IS NULL."""
        stmt = (
            select(OpticalThresholdPolicy)
            .where(OpticalThresholdPolicy.scope_type == scope_type)
            .where(OpticalThresholdPolicy.metric_name == metric_name)
            .where(OpticalThresholdPolicy.active.is_(True))
        )
        if scope_id is None:
            stmt = stmt.where(OpticalThresholdPolicy.scope_id.is_(None))
        else:
            stmt = stmt.where(OpticalThresholdPolicy.scope_id == scope_id)

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_page(
        self,
        *,
        offset: int,
        limit: int,
        scope_type: OpticalScopeType | None,
        metric_name: str | None,
        active_only: bool,
    ) -> tuple[Sequence[OpticalThresholdPolicy], int]:
        base = select(OpticalThresholdPolicy)
        if scope_type is not None:
            base = base.where(OpticalThresholdPolicy.scope_type == scope_type)
        if metric_name is not None:
            base = base.where(OpticalThresholdPolicy.metric_name == metric_name)
        if active_only:
            base = base.where(OpticalThresholdPolicy.active.is_(True))

        items_stmt = (
            base.order_by(
                OpticalThresholdPolicy.scope_type.asc(),
                OpticalThresholdPolicy.metric_name.asc(),
            )
            .offset(offset)
            .limit(limit)
        )
        items_result = await self._session.execute(items_stmt)
        items = items_result.scalars().all()

        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await self._session.execute(count_stmt)).scalar_one()

        return items, int(total)

    async def list_active_for_chain(
        self,
        *,
        onu_id: UUID,
        pon_port_id: UUID,
        olt_id: UUID,
    ) -> Sequence[OpticalThresholdPolicy]:
        """Carrega TODAS as políticas ativas que podem afetar uma ONU,
        nos 4 escopos da hierarquia. Serviço de resolução hierárquica
        escolhe a mais específica por métrica em memória.
        Uma única query, alimenta o cache do worker."""
        stmt = (
            select(OpticalThresholdPolicy)
            .where(OpticalThresholdPolicy.active.is_(True))
            .where(
                or_(
                    # ONU específica
                    (OpticalThresholdPolicy.scope_type == OpticalScopeType.ONU)
                    & (OpticalThresholdPolicy.scope_id == onu_id),
                    # PON específica
                    (OpticalThresholdPolicy.scope_type == OpticalScopeType.PON_PORT)
                    & (OpticalThresholdPolicy.scope_id == pon_port_id),
                    # OLT específica
                    (OpticalThresholdPolicy.scope_type == OpticalScopeType.OLT)
                    & (OpticalThresholdPolicy.scope_id == olt_id),
                    # Global
                    OpticalThresholdPolicy.scope_type == OpticalScopeType.GLOBAL,
                )
            )
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def add(self, policy: OpticalThresholdPolicy) -> None:
        self._session.add(policy)
        await self._session.flush()
