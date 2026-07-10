import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID

import structlog
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.pagination import Page, PageParams
from app.domains.inventory.models.chassis import Chassis
from app.domains.inventory.models.line_profile import LineProfile
from app.domains.inventory.models.olt_model import OltModel
from app.domains.inventory.models.onu import Onu
from app.domains.inventory.models.pon_port import PonPort
from app.domains.inventory.models.service_profile import ServiceProfile
from app.domains.inventory.models.slot import Slot
from app.domains.inventory.models.vlan import Vlan
from app.domains.inventory.repositories.olt import OltRepository
from app.domains.provisioning.enums import (
    TERMINAL_PROVISIONING_STATUSES,
    ProvisioningStatus,
)
from app.domains.provisioning.exceptions import (
    LineProfileReferenceInvalid,
    OnuIndexConflict,
    PonPortReferenceInvalid,
    ProvisioningOrderActiveConflict,
    ProvisioningOrderIdempotencyConflict,
    ProvisioningOrderIdempotencyPayloadMismatch,
    ProvisioningOrderNotCancelable,
    ProvisioningOrderNotFound,
    ProvisioningTemplateReferenceInvalid,
    RetryOfOrderInvalid,
    SerialNotRecognized,
    ServiceProfileReferenceInvalid,
    VlanReferenceInvalid,
)
from app.domains.provisioning.models.provisioning_order import ProvisioningOrder
from app.domains.provisioning.models.provisioning_template import ProvisioningTemplate
from app.domains.provisioning.repositories.provisioning_order import (
    ProvisioningOrderRepository,
)
from app.domains.provisioning.repositories.provisioning_rollback import (
    ProvisioningRollbackRepository,
)
from app.domains.provisioning.repositories.provisioning_step import (
    ProvisioningStepRepository,
)
from app.domains.provisioning.schemas.provisioning_order import (
    ProvisioningOrderCreate,
    ProvisioningOrderDetailRead,
    ProvisioningOrderRead,
)
from app.domains.provisioning.schemas.provisioning_rollback import (
    ProvisioningRollbackRead,
)
from app.domains.provisioning.schemas.provisioning_step import ProvisioningStepRead
from app.domains.provisioning.schemas.snapshot_params import (
    SnapshotParams,  # noqa: F401
    SnapshotStored,
)

log = structlog.get_logger(__name__)

# Nomes dos índices únicos (para _violated_constraint)
_UQ_IDEMPOTENCY = "uq_provisioning_idempotency"
_UQ_PROV_ACTIVE = "uq_prov_order_active_unique"

# Estados de pending_onu considerados ainda ativos para o reconhecimento de serial.
_ACTIVE_PENDING_ONU_STATES = ("detected", "waiting")


def _violated_constraint(orig: str) -> str | None:
    if _UQ_IDEMPOTENCY in orig:
        return _UQ_IDEMPOTENCY
    if _UQ_PROV_ACTIVE in orig:
        return _UQ_PROV_ACTIVE
    return None


def _compute_payload_hash(payload: ProvisioningOrderCreate) -> str:
    """Hash canônico do payload para idempotência."""
    data = payload.model_dump(mode="json")
    data.pop("idempotency_key", None)
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)  # noqa: UP017


class ProvisioningOrderService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = ProvisioningOrderRepository(session)
        self._step_repo = ProvisioningStepRepository(session)
        self._rollback_repo = ProvisioningRollbackRepository(session)

    # READ
    async def get_detail(
        self, provisioning_order_id: UUID, *, actor: Actor
    ) -> ProvisioningOrderDetailRead:
        del actor
        order = await self._repo.get_by_id(provisioning_order_id)
        if order is None:
            raise ProvisioningOrderNotFound(provisioning_order_id)
        return await self._build_detail(order)

    async def list_page(
        self,
        *,
        params: PageParams,
        olt_id: UUID | None,
        status_filter: ProvisioningStatus | None,
        app_user_id: UUID | None,
        created_from: datetime | None,
        created_to: datetime | None,
        actor: Actor,
    ) -> Page[ProvisioningOrderRead]:
        del actor
        items, total = await self._repo.list_page(
            limit=params.limit,
            offset=params.offset,
            olt_id=olt_id,
            status_filter=status_filter,
            app_user_id=app_user_id,
            created_from=created_from,
            created_to=created_to,
        )
        return Page[ProvisioningOrderRead](
            items=[ProvisioningOrderRead.model_validate(o) for o in items],
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    async def _build_detail(self, order: ProvisioningOrder) -> ProvisioningOrderDetailRead:
        steps = await self._step_repo.list_for_order(order.provisioning_order_id)
        rollback = await self._rollback_repo.get_for_order(order.provisioning_order_id)
        return ProvisioningOrderDetailRead(
            **ProvisioningOrderRead.model_validate(order).model_dump(),
            steps=[ProvisioningStepRead.model_validate(s) for s in steps],
            rollback=(
                ProvisioningRollbackRead.model_validate(rollback) if rollback is not None else None
            ),
        )

    # CREATE
    async def create_order(
        self,
        *,
        payload: ProvisioningOrderCreate,
        actor: Actor,
    ) -> tuple[ProvisioningOrderDetailRead, bool]:
        """Cria uma ordem em 'pending' ou devolve a existente na idempotência."""
        payload_hash = _compute_payload_hash(payload)

        # V0 (idempotência): key existe?
        existing_by_key = await self._repo.get_by_idempotency_key(payload.idempotency_key)
        if existing_by_key is not None:
            reused_order = self._resolve_idempotent_hit(
                existing=existing_by_key,
                incoming_key=payload.idempotency_key,
                incoming_hash=payload_hash,
            )
            detail = await self._build_detail(reused_order)
            return detail, True

        # V1: OLT viva
        olt = await OltRepository(self._session).get_by_id(payload.olt_id)
        if olt is None:
            raise PonPortReferenceInvalid(
                payload.pon_port_id, reason="olt_id da ordem não existe ou está removida"
            )

        # V2: pon_port pertence à olt
        pon_row = await self._session.execute(
            select(PonPort, Slot.slot_index, PonPort.pon_index)
            .join(Slot, Slot.slot_id == PonPort.slot_id)
            .where(PonPort.pon_port_id == payload.pon_port_id)
        )
        pon_data = pon_row.first()
        if pon_data is None:
            raise PonPortReferenceInvalid(payload.pon_port_id, reason="pon_port_id inexistente")
        pon_port: PonPort = pon_data[0]
        chassis_check = await self._session.execute(
            select(Slot).where(Slot.slot_id == pon_port.slot_id)
        )
        slot_obj = chassis_check.scalar_one_or_none()
        if slot_obj is None:
            raise PonPortReferenceInvalid(
                payload.pon_port_id, reason="slot da pon_port não encontrado"
            )
        chassis_obj = (
            await self._session.execute(
                select(Chassis).where(Chassis.chassis_id == slot_obj.chassis_id)
            )
        ).scalar_one_or_none()
        if chassis_obj is None or chassis_obj.olt_id != payload.olt_id:
            raise PonPortReferenceInvalid(
                payload.pon_port_id, reason="pon_port não pertence à olt_id informada"
            )

        # V3: line_profile / service_profile / vlan
        snap = payload.snapshot
        line_profile = await self._session.get(LineProfile, snap.line_profile_id)
        if line_profile is None or line_profile.olt_id != payload.olt_id:
            raise LineProfileReferenceInvalid(
                snap.line_profile_id, reason="não pertence à olt_id da ordem"
            )
        if not line_profile.active:
            raise LineProfileReferenceInvalid(snap.line_profile_id, reason="inativo")

        service_profile = await self._session.get(ServiceProfile, snap.service_profile_id)
        if service_profile is None or service_profile.olt_id != payload.olt_id:
            raise ServiceProfileReferenceInvalid(
                snap.service_profile_id, reason="não pertence à olt_id da ordem"
            )
        if not service_profile.active:
            raise ServiceProfileReferenceInvalid(snap.service_profile_id, reason="inativo")

        vlan = await self._session.get(Vlan, snap.vlan_id)
        if vlan is None or vlan.olt_id != payload.olt_id:
            raise VlanReferenceInvalid(snap.vlan_id, reason="não pertence à olt_id da ordem")
        if not vlan.active:
            raise VlanReferenceInvalid(snap.vlan_id, reason="inativa")

        # V4: template
        template = await self._session.get(ProvisioningTemplate, payload.provisioning_template_id)
        if template is None:
            raise ProvisioningTemplateReferenceInvalid(
                payload.provisioning_template_id, reason="inexistente"
            )
        if not template.active:
            raise ProvisioningTemplateReferenceInvalid(
                payload.provisioning_template_id, reason="inativo"
            )
        olt_model = await self._session.get(OltModel, olt.olt_model_id)
        if olt_model is None:
            raise ProvisioningTemplateReferenceInvalid(
                payload.provisioning_template_id,
                reason="olt_model da olt não encontrado",
            )
        if template.manufacturer_id != olt_model.manufacturer_id:
            raise ProvisioningTemplateReferenceInvalid(
                payload.provisioning_template_id,
                reason="manufacturer do template diverge do fabricante da OLT",
            )
        if template.olt_model_id is not None and template.olt_model_id != olt.olt_model_id:
            raise ProvisioningTemplateReferenceInvalid(
                payload.provisioning_template_id,
                reason="olt_model do template diverge do modelo da OLT",
            )

        # V5: retry_of_order_id (opcional)
        if payload.retry_of_order_id is not None:
            retry_src = await self._repo.get_by_id(payload.retry_of_order_id)
            if retry_src is None:
                raise RetryOfOrderInvalid(payload.retry_of_order_id, reason="inexistente")
            if retry_src.status not in TERMINAL_PROVISIONING_STATUSES:
                raise RetryOfOrderInvalid(
                    payload.retry_of_order_id,
                    reason=(f"ordem original em estado não terminal ({retry_src.status.value})"),
                )

        # V6: serial reconhecido
        existing_onu_by_serial = (
            await self._session.execute(
                select(Onu).where(Onu.serial == payload.serial, Onu.deleted_at.is_(None))
            )
        ).scalar_one_or_none()
        onu_id_for_order: UUID | None = None
        if existing_onu_by_serial is not None:
            onu_id_for_order = existing_onu_by_serial.onu_id
        else:
            pending_row = (
                await self._session.execute(
                    text(
                        """
                        SELECT 1
                        FROM pending_onu
                        WHERE serial = :serial
                        AND pon_port_id = :pon_id
                        AND state = ANY(:states)
                        LIMIT 1
                        """
                    ),
                    {
                        "serial": payload.serial,
                        "pon_id": str(payload.pon_port_id),
                        "states": list(_ACTIVE_PENDING_ONU_STATES),
                    },
                )
            ).first()
            if pending_row is None:
                raise SerialNotRecognized(payload.serial)

        # V7: onu_index não colide
        colliding_onu = (
            await self._session.execute(
                select(Onu).where(
                    Onu.pon_port_id == payload.pon_port_id,
                    Onu.onu_index == snap.onu_index,
                    Onu.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if colliding_onu is not None and (
            onu_id_for_order is None or colliding_onu.onu_id != onu_id_for_order
        ):
            raise OnuIndexConflict(
                pon_port_id=payload.pon_port_id,
                onu_index=snap.onu_index,
                existing_onu_id=colliding_onu.onu_id,
            )

        # V8: uq_prov_order_active_unique
        if onu_id_for_order is not None:  # noqa: SIM102
            if await self._repo.has_active_for_onu(onu_id_for_order):
                raise ProvisioningOrderActiveConflict(onu_id_for_order)

        # Denormalização
        snapshot_stored = SnapshotStored(
            line_profile_id=snap.line_profile_id,
            service_profile_id=snap.service_profile_id,
            vlan_id=snap.vlan_id,
            onu_index=snap.onu_index,
            custom_id=snap.custom_id,
            external_customer_id=snap.external_customer_id,
            serial=payload.serial,
            vlan_number=vlan.vlan_number,
            line_profile_name=line_profile.name,
            service_profile_name=service_profile.name,
        )

        # INSERT
        order = ProvisioningOrder(
            olt_id=payload.olt_id,
            pon_port_id=payload.pon_port_id,
            onu_id=onu_id_for_order,
            app_user_id=actor.actor_id,
            provisioning_template_id=payload.provisioning_template_id,
            retry_of_order_id=payload.retry_of_order_id,
            idempotency_key=payload.idempotency_key,
            idempotency_payload_hash=payload_hash,
            snapshot_params=snapshot_stored.model_dump(mode="json"),
        )
        idempotency_key_local = payload.idempotency_key
        onu_id_local = onu_id_for_order

        try:
            await self._repo.add(order)
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            constraint = _violated_constraint(str(exc.orig))
            if constraint == _UQ_IDEMPOTENCY:
                existing = await self._repo.get_by_idempotency_key(idempotency_key_local)
                if existing is not None:
                    reused_order = self._resolve_idempotent_hit(
                        existing=existing,
                        incoming_key=idempotency_key_local,
                        incoming_hash=payload_hash,
                    )
                    detail = await self._build_detail(reused_order)
                    return detail, True
                raise ProvisioningOrderIdempotencyConflict(idempotency_key_local) from exc
            if constraint == _UQ_PROV_ACTIVE and onu_id_local is not None:
                raise ProvisioningOrderActiveConflict(onu_id_local) from exc
            raise

        await self._session.refresh(order)

        log.info(
            "provisioning_order.created",
            provisioning_order_id=str(order.provisioning_order_id),
            olt_id=str(payload.olt_id),
            pon_port_id=str(payload.pon_port_id),
            template_id=str(payload.provisioning_template_id),
            onu_id=str(onu_id_for_order) if onu_id_for_order else None,
            serial=payload.serial,
            payload_hash=payload_hash,
            actor=str(actor),
        )

        detail = await self._build_detail(order)
        return detail, False  # was_reused

    def _resolve_idempotent_hit(
        self,
        *,
        existing: ProvisioningOrder,
        incoming_key: str,
        incoming_hash: str,
    ) -> ProvisioningOrder:
        """Decide reuso vs mismatch para uma ordem já existente com o
        mesmo idempotency_key."""
        existing_hash = existing.idempotency_payload_hash
        if existing_hash is None or existing_hash == incoming_hash:
            log.info(
                "provisioning_order.idempotent_hit",
                provisioning_order_id=str(existing.provisioning_order_id),
                idempotency_key=incoming_key,
                legacy_no_hash=existing_hash is None,
            )
            return existing
        raise ProvisioningOrderIdempotencyPayloadMismatch(incoming_key)

    # CANCEL
    async def cancel_order(
        self,
        provisioning_order_id: UUID,
        *,
        actor: Actor,
    ) -> ProvisioningOrderDetailRead:
        """Cancela ordem em estado 'pending'"""
        stmt = (
            select(ProvisioningOrder)
            .where(ProvisioningOrder.provisioning_order_id == provisioning_order_id)
            .with_for_update()
        )
        order = (await self._session.execute(stmt)).scalar_one_or_none()
        if order is None:
            raise ProvisioningOrderNotFound(provisioning_order_id)

        if order.status != ProvisioningStatus.PENDING:
            raise ProvisioningOrderNotCancelable(provisioning_order_id, order.status.value)

        order.status = ProvisioningStatus.CANCELED
        order.finished_at = _utcnow()
        order.failure_reason = f"canceled by {actor}"
        await self._session.commit()
        await self._session.refresh(order)

        log.info(
            "provisioning_order.canceled",
            provisioning_order_id=str(provisioning_order_id),
            actor=str(actor),
        )
        return await self._build_detail(order)
