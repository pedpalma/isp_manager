# Service de OpticalThresholdPolicy.
# Responsabilidades:
# - validar scope_id obrigatório quando scope != 'global' (BadRequest 400)
# - validar metric_name no conjunto suportado (ValidationError 422)
# - validar at least one threshold (validation 422: CHECK do DDL exige)
# - pre-check de unicidade hierárquica (Conflict 409)
# - catch IntegrityError genérico no INSERT (covers race SELECT->INSERT)
# - UPDATE sem try/except: nenhum campo de unicidade no Update
#   (scope_type/scope_id/metric_name são imutáveis); active e booleano
#   simples que pode acionar a unicidade parcial somente em INSERT.
#   Atenção: reativar (active false -> true) PODE colidir; sera tratado
#   como caso especial.

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.exceptions import ValidationError
from app.core.pagination import Page, PageParams
from app.domains.optical.enums import (
    SUPPORTED_OPTICAL_METRICS,
    OpticalScopeType,
)
from app.domains.optical.exceptions import (
    OpticalMetricInvalid,
    OpticalScopeMismatch,
    OpticalThresholdPolicyConflict,
    OpticalThresholdPolicyNotFound,
)
from app.domains.optical.models.optical_threshold_policy import (
    OpticalThresholdPolicy,
)
from app.domains.optical.repositories.optical_threshold_policy import (
    OpticalThresholdPolicyRepository,
)
from app.domains.optical.schemas.optical_threshold_policy import (
    OpticalThresholdPolicyCreate,
    OpticalThresholdPolicyRead,
    OpticalThresholdPolicyUpdate,
)

log = structlog.get_logger(__name__)


class OpticalThresholdPolicyService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = OpticalThresholdPolicyRepository(session)

    async def get(self, policy_id: UUID, *, actor: Actor) -> OpticalThresholdPolicyRead:
        del actor
        policy = await self._repo.get_by_id(policy_id)
        if policy is None:
            raise OpticalThresholdPolicyNotFound(policy_id)
        return OpticalThresholdPolicyRead.model_validate(policy)

    async def list_page(
        self,
        *,
        params: PageParams,
        scope_type: OpticalScopeType | None,
        metric_name: str | None,
        active_only: bool,
        actor: Actor,
    ) -> Page[OpticalThresholdPolicyRead]:
        del actor
        items, total = await self._repo.list_page(
            offset=params.offset,
            limit=params.limit,
            scope_type=scope_type,
            metric_name=metric_name,
            active_only=active_only,
        )
        return Page[OpticalThresholdPolicyRead](
            items=[OpticalThresholdPolicyRead.model_validate(p) for p in items],
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    async def create(
        self,
        payload: OpticalThresholdPolicyCreate,
        *,
        actor: Actor,
    ) -> OpticalThresholdPolicyRead:
        # 1. Válida metric_name
        if payload.metric_name not in SUPPORTED_OPTICAL_METRICS:
            raise OpticalMetricInvalid(payload.metric_name)

        # 2. Válida scope_id consistente com scope_type
        is_global = payload.scope_type == OpticalScopeType.GLOBAL
        has_scope_id = payload.scope_id is not None
        if is_global and has_scope_id:
            raise OpticalScopeMismatch(payload.scope_type.value, has_scope_id=True)
        if not is_global and not has_scope_id:
            raise OpticalScopeMismatch(payload.scope_type.value, has_scope_id=False)

        # 3. Válida que ao menos um threshold está presente (CHECK do DDL)
        if payload.threshold_min is None and payload.threshold_max is None:
            raise ValidationError(
                "threshold_min ou threshold_max devem ser informados.",
                details={
                    "threshold_min": None,
                    "threshold_max": None,
                },
            )

        # 4. Pre-check de unicidade hierárquica
        existing = await self._repo.get_active_by_scope_and_metric(
            scope_type=payload.scope_type,
            scope_id=payload.scope_id,
            metric_name=payload.metric_name,
        )
        if existing is not None:
            raise OpticalThresholdPolicyConflict(
                payload.scope_type.value,
                payload.scope_id,
                payload.metric_name,
            )

        # 5. Insert
        policy = OpticalThresholdPolicy(
            scope_type=payload.scope_type,
            scope_id=payload.scope_id,
            metric_name=payload.metric_name,
            threshold_min=payload.threshold_min,
            threshold_max=payload.threshold_max,
            severity=payload.severity,
            active=payload.active,
        )
        try:
            await self._repo.add(policy)
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            # Cobre corrida SELECT->INSERT na unicidade parcial.
            raise OpticalThresholdPolicyConflict(
                payload.scope_type.value,
                payload.scope_id,
                payload.metric_name,
            ) from exc

        await self._session.refresh(policy)
        log.info(
            "optical_threshold_policy.created",
            optical_threshold_policy_id=str(policy.optical_threshold_policy_id),
            scope_type=payload.scope_type.value,
            scope_id=str(payload.scope_id) if payload.scope_id else None,
            metric_name=payload.metric_name,
            actor=str(actor),
        )
        return OpticalThresholdPolicyRead.model_validate(policy)

    async def update(
        self,
        policy_id: UUID,
        payload: OpticalThresholdPolicyUpdate,
        *,
        actor: Actor,
    ) -> OpticalThresholdPolicyRead:
        policy = await self._repo.get_by_id(policy_id)
        if policy is None:
            raise OpticalThresholdPolicyNotFound(policy_id)

        data = payload.model_dump(exclude_unset=True)
        if not data:
            return OpticalThresholdPolicyRead.model_validate(policy)

        # Re-ativação de policy pode colidir com outra já ativa (parcial
        # unique cobre apenas WHERE active=TRUE). Tratamos como Conflict.
        reactivating = data.get("active") is True and policy.active is False
        if reactivating:
            existing = await self._repo.get_active_by_scope_and_metric(
                scope_type=policy.scope_type,
                scope_id=policy.scope_id,
                metric_name=policy.metric_name,
            )
            if (
                existing is not None
                and existing.optical_threshold_policy_id != policy.optical_threshold_policy_id
            ):
                raise OpticalThresholdPolicyConflict(
                    policy.scope_type.value,
                    policy.scope_id,
                    policy.metric_name,
                )

        for field, value in data.items():
            setattr(policy, field, value)

        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise OpticalThresholdPolicyConflict(
                policy.scope_type.value,
                policy.scope_id,
                policy.metric_name,
            ) from exc

        await self._session.refresh(policy)
        log.info(
            "optical_threshold_policy.updated",
            optical_threshold_policy_id=str(policy.optical_threshold_policy_id),
            fields=list(data.keys()),
            actor=str(actor),
        )
        return OpticalThresholdPolicyRead.model_validate(policy)
