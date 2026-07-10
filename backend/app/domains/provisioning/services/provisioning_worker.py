# Worker síncrono do ciclo de provisionamento de ONUs.

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.adapters.olt.base import (
    OltConnectionConfig,
    OnuLocator,
    PlannedCommand,
    ProvisioningPlan,
    ProvisioningResult,
    StepResult,
)
from app.adapters.olt.factory import get_olt_adapter
from app.core.config import settings
from app.db.session_sync import session_scope
from app.domains.collection.services._worker_common import (
    OltLockUnavailable,
    acquire_olt_advisory_lock,
    build_connection_config,
    load_olt_and_credential,
)
from app.domains.inventory.models.olt_model import OltModel
from app.domains.inventory.models.onu import Onu
from app.domains.provisioning.enums import (
    ProvisioningStatus,
    RollbackStatus,
    StepPhase,
)
from app.domains.provisioning.models.normalized_command import NormalizedCommand
from app.domains.provisioning.models.provisioning_order import ProvisioningOrder
from app.domains.provisioning.models.provisioning_rollback import ProvisioningRollback
from app.domains.provisioning.models.provisioning_step import ProvisioningStep
from app.domains.provisioning.models.provisioning_template import ProvisioningTemplate
from app.domains.provisioning.services.command_cache import (
    CacheKey,
    CommandCache,
    NormalizedCommandResolved,
    is_miss,
)

log = structlog.get_logger(__name__)


# Hard limit para output_received antes da gravação em provisioning_step.
# 64KB é suficiente para auditoria sem inchar a tabela.
MAX_OUTPUT_LENGTH = 65_536
_TRUNCATION_SUFFIX = "\n... [output truncated]"


# Singleton de módulo.
_COMMAND_CACHE = CommandCache(
    ttl_seconds=getattr(
        settings.provisioning,
        "command_cache_ttl_seconds",
        60,
    )
)


class _ProvisioningAborted(Exception):
    """Marcador interno: o ciclo não deve continuar mas a ordem já foi
    devidamente marcada em outro lugar."""


class _ValidationFailure(Exception):
    """Falha em fase 1 antes de qualquer SSH. Contém a mensagem que vira
    failure_reason da ordem. Não requer rollback."""


@dataclass(frozen=True, slots=True)
class _LoadedContext:
    """Snapshot imutável do que a fase 1 carrega para as fases seguintes."""

    order_id: UUID
    olt_id: UUID
    connection_config: OltConnectionConfig
    locator: OnuLocator
    plan: ProvisioningPlan
    rollback_command_keys: dict[str, str]
    step_key_by_order: dict[int, str]
    manufacturer_slug: str | None


def _truncate(value: str | None) -> str | None:
    if value is None:
        return None
    if len(value) <= MAX_OUTPUT_LENGTH:
        return value
    return value[:MAX_OUTPUT_LENGTH] + _TRUNCATION_SUFFIX


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)  # noqa: UP017


# Ponto de entrada chamado pela task Celery.
def run_provisioning_order_sync(order_id: UUID) -> None:
    """Executa o ciclo completo. Nunca propaga exception."""
    log.info("provisioning.worker.started", provisioning_order_id=str(order_id))

    # Fase 1: lock + load + validate + marca validating.
    try:
        ctx = _phase_load_lock_and_validate(order_id)
    except _ProvisioningAborted:
        return
    except OltLockUnavailable as exc:
        log.warning(
            "provisioning.worker.lock_unavailable",
            provisioning_order_id=str(order_id),
            error=str(exc),
        )
        _mark_failed(order_id, f"phase1: {exc}")
        return
    except _ValidationFailure as exc:
        log.warning(
            "provisioning.worker.validation_failed",
            provisioning_order_id=str(order_id),
            reason=str(exc),
        )
        return
    except Exception as exc:
        log.exception(
            "provisioning.worker.phase1_failed",
            provisioning_order_id=str(order_id),
            error=str(exc),
        )
        _mark_failed(order_id, f"phase1: {exc}")
        return

    try:
        _mark_running(ctx.order_id)  # transição validating -> running
        adapter = get_olt_adapter(manufacturer_slug=ctx.manufacturer_slug)
        result = adapter.provision_onu(
            ctx.connection_config,
            ctx.plan,
            olt_id=ctx.olt_id,
        )
    except Exception as exc:
        log.exception(
            "provisioning.worker.phase2_failed",
            provisioning_order_id=str(order_id),
            olt_id=str(ctx.olt_id),
            manufacturer_slug=ctx.manufacturer_slug,
            error=str(exc),
        )
        _mark_failed(order_id, f"phase2: {exc}")
        return

    # Fase 3: grava steps + decide status.
    try:
        outcome = _phase_persist_results(ctx=ctx, result=result)
    except Exception as exc:
        log.exception(
            "provisioning.worker.phase3_failed",
            provisioning_order_id=str(order_id),
            olt_id=str(ctx.olt_id),
            error=str(exc),
        )
        _mark_failed(order_id, f"phase3: {exc}")
        return

    # Se persist decidiu rollback: fase 4.
    if outcome.needs_rollback:
        try:
            _phase_rollback(ctx=ctx, outcome=outcome)
        except Exception as exc:
            log.exception(
                "provisioning.worker.phase4_failed",
                provisioning_order_id=str(order_id),
                olt_id=str(ctx.olt_id),
                error=str(exc),
            )
            _mark_failed(
                order_id,
                f"phase4 (rollback): {exc}",
            )
            return
        # Rollback já finalizou a ordem em ROLLED_BACK ou FAILED.
        return

    # Sem rollback: finaliza direto conforme o outcome.
    _finalize(order_id, outcome)


# Fase 1
def _phase_load_lock_and_validate(order_id: UUID) -> _LoadedContext:
    """Fase 1 completa em uma transação."""
    validation_error: str | None = None
    context: _LoadedContext | None = None

    with session_scope() as db:
        try:
            order = _lock_pending_order(db, order_id)
            acquire_olt_advisory_lock(db, order.olt_id)
            olt, credential = load_olt_and_credential(db, order.olt_id)
            connection_config = build_connection_config(olt, credential)

            template = _load_active_template(db, order.provisioning_template_id)
            raw = template.raw_template

            missing = _snapshot_missing_required(order, raw)
            if missing:
                raise _ValidationFailure("snapshot_params ausente de: " + ", ".join(missing))

            olt_model_id = _load_olt_model_id(db, olt.olt_model_id)
            manufacturer_slug = _load_manufacturer_slug_by_olt_model(db, olt_model_id)
            manufacturer_id = template.manufacturer_id
            version_constraint = raw.get("version_constraint")

            planned: list[PlannedCommand] = []
            step_key_by_order: dict[int, str] = {}
            rollback_command_keys: dict[str, str] = dict(raw.get("rollback_map") or {})

            for idx, step_def in enumerate(raw.get("steps") or [], start=1):
                step_key = str(step_def["step_key"])
                command_key = str(step_def["command_key"])
                step_key_by_order[idx] = step_key

                resolved = _resolve_normalized_command(
                    db,
                    manufacturer_id=manufacturer_id,
                    olt_model_id=olt_model_id,
                    command_key=command_key,
                    version_constraint=version_constraint,
                )
                if resolved is None:
                    raise _ValidationFailure(
                        f"command_key {command_key!r} sem correspondência ativa "
                        f"em normalized_command"
                    )

                rendered = _render_command(
                    template_string=resolved.template_string,
                    snapshot=dict(order.snapshot_params or {}),
                    command_vars=dict(template.command_vars or {}),
                )
                planned.append(
                    PlannedCommand(
                        command_key=command_key,
                        rendered=rendered,
                        timeout_ms=int(resolved.timeout_ms),
                    )
                )

            onu_index = int((order.snapshot_params or {}).get("onu_index") or 0)
            serial = _load_onu_serial(db, order.onu_id) if order.onu_id else None
            slot_index, pon_index = _load_slot_and_pon_indexes(db, order.pon_port_id)
            locator = OnuLocator(
                slot_index=slot_index,
                pon_index=pon_index,
                serial=serial,
                onu_index=onu_index or None,
            )
            plan = ProvisioningPlan(locator=locator, commands=planned)

            # Marca validating + started_at (running vem quando SSH inicia).
            order.status = ProvisioningStatus.VALIDATING
            order.started_at = _utcnow()

            context = _LoadedContext(
                order_id=order.provisioning_order_id,
                olt_id=order.olt_id,
                connection_config=connection_config,
                locator=locator,
                plan=plan,
                rollback_command_keys=rollback_command_keys,
                step_key_by_order=step_key_by_order,
                manufacturer_slug=manufacturer_slug,
            )
        except _ValidationFailure as vf:
            validation_error = str(vf)
            _mark_validation_failure_in_session(
                db,
                order=order,  # noqa: F821 (order sempre definido antes deste catch)
                reason=validation_error,
            )

    if validation_error is not None:
        raise _ValidationFailure(validation_error)
    assert context is not None, "invariante: sem erro implica contexto pronto"
    return context


def _lock_pending_order(db: Session, order_id: UUID) -> ProvisioningOrder:
    """SELECT ... FOR UPDATE. Aborta se a ordem não estiver PENDING."""
    stmt = (
        select(ProvisioningOrder)
        .where(ProvisioningOrder.provisioning_order_id == order_id)
        .with_for_update()
    )
    order = db.execute(stmt).scalar_one_or_none()
    if order is None:
        log.error(
            "provisioning.worker.order_not_found",
            provisioning_order_id=str(order_id),
        )
        raise _ProvisioningAborted()
    if order.status != ProvisioningStatus.PENDING:
        log.warning(
            "provisioning.worker.order_not_pending",
            provisioning_order_id=str(order_id),
            current_status=str(order.status),
        )
        raise _ProvisioningAborted()
    return order


def _load_active_template(db: Session, template_id: UUID) -> ProvisioningTemplate:
    stmt = select(ProvisioningTemplate).where(
        ProvisioningTemplate.provisioning_template_id == template_id,
        ProvisioningTemplate.active.is_(True),
    )
    template = db.execute(stmt).scalar_one_or_none()
    if template is None:
        raise _ValidationFailure(f"provisioning_template {template_id} inativo ou inexistente")
    return template


def _load_olt_model_id(db: Session, olt_model_id: UUID | None) -> UUID | None:
    if olt_model_id is None:
        return None
    stmt = select(OltModel.olt_model_id).where(OltModel.olt_model_id == olt_model_id)
    return db.execute(stmt).scalar_one_or_none()


def _load_manufacturer_slug_by_olt_model(db: Session, olt_model_id: UUID | None) -> str | None:
    """Resolve o slug do manufacturer a partir do olt_model_id."""
    if olt_model_id is None:
        return None
    row = db.execute(
        text(
            """
            SELECT m.slug
            FROM olt_model om
            JOIN manufacturer m ON m.manufacturer_id = om.manufacturer_id
            WHERE om.olt_model_id = :olt_model_id
            """
        ),
        {"olt_model_id": str(olt_model_id)},
    ).first()
    return row[0] if row is not None else None


def _load_onu_serial(db: Session, onu_id: UUID) -> str | None:
    stmt = select(Onu.serial).where(Onu.onu_id == onu_id)
    return db.execute(stmt).scalar_one_or_none()


def _load_slot_and_pon_indexes(db: Session, pon_port_id: UUID) -> tuple[int, int]:
    """Resolve (slot_index, pon_index) a partir do pon_port_id."""
    row = db.execute(
        text(
            """
            SELECT s.slot_index, pp.pon_index
            FROM pon_port pp
            JOIN slot s ON s.slot_id = pp.slot_id
            WHERE pp.pon_port_id = :id
            """
        ),
        {"id": str(pon_port_id)},
    ).first()
    if row is None:
        raise _ValidationFailure(f"pon_port {pon_port_id} não encontrado no inventário")
    return int(row[0]), int(row[1])


def _snapshot_missing_required(
    order: ProvisioningOrder,
    raw: dict[str, Any],
) -> list[str]:
    params_schema = raw.get("params_schema") or {}
    snapshot = order.snapshot_params or {}
    missing: list[str] = []
    for name, spec in params_schema.items():
        if not isinstance(spec, dict):
            continue
        if not bool(spec.get("required", False)):
            continue
        if name not in snapshot:
            missing.append(name)
    return missing


def _mark_validation_failure_in_session(
    db: Session,
    *,
    order: ProvisioningOrder,
    reason: str,
) -> None:
    """Grava step de validação (success=false) e marca a ordem como FAILED"""
    db.add(
        ProvisioningStep(
            provisioning_order_id=order.provisioning_order_id,
            step_order=0,
            step_key="__validation__",
            phase=StepPhase.VALIDATION.value,
            command_sent=None,
            output_received=_truncate(reason),
            parser_output=None,
            success=False,
            duration_ms=None,
        )
    )
    order.status = ProvisioningStatus.FAILED
    order.finished_at = _utcnow()
    order.failure_reason = reason[:1000]


# Resolução de comando via cache
def _resolve_normalized_command(
    db: Session,
    *,
    manufacturer_id: UUID,
    olt_model_id: UUID | None,
    command_key: str,
    version_constraint: str | None,
) -> NormalizedCommandResolved | None:
    """Cache-aside: consulta cache in-process; se miss, busca DB e cacheia."""
    key: CacheKey = (manufacturer_id, olt_model_id, command_key, version_constraint)
    cached = _COMMAND_CACHE.get(key)
    if not is_miss(cached):
        return cached  # type: ignore[return-value]

    resolved = _query_normalized_command(
        db,
        manufacturer_id=manufacturer_id,
        olt_model_id=olt_model_id,
        command_key=command_key,
        version_constraint=version_constraint,
    )
    _COMMAND_CACHE.put(key, resolved)
    return resolved


def _query_normalized_command(
    db: Session,
    *,
    manufacturer_id: UUID,
    olt_model_id: UUID | None,
    command_key: str,
    version_constraint: str | None,
) -> NormalizedCommandResolved | None:
    stmt = (
        select(
            NormalizedCommand.normalized_command_id,
            NormalizedCommand.olt_model_id,
            NormalizedCommand.template_string,
            NormalizedCommand.output_parser,
            NormalizedCommand.timeout_ms,
            NormalizedCommand.requires_privileged,
            NormalizedCommand.version_constraint,
        )
        .where(
            NormalizedCommand.manufacturer_id == manufacturer_id,
            NormalizedCommand.command_key == command_key,
            NormalizedCommand.active.is_(True),
        )
        .order_by(
            # Prioriza matches específicos ao modelo antes de manufacturer-wide.
            NormalizedCommand.olt_model_id.desc().nullslast(),
        )
        .limit(8)
    )
    rows = db.execute(stmt).all()
    if not rows:
        return None

    # Primeira passada: match específico ao olt_model.
    if olt_model_id is not None:
        for row in rows:
            if row.olt_model_id == olt_model_id and _row_version_matches(
                row.version_constraint, version_constraint
            ):
                return _build_resolved(row)

    # Segunda passada: manufacturer-wide (olt_model_id IS NULL).
    for row in rows:
        if row.olt_model_id is None and _row_version_matches(
            row.version_constraint, version_constraint
        ):
            return _build_resolved(row)

    return None


def _row_version_matches(
    row_version_constraint: str | None,
    requested_version_constraint: str | None,
) -> bool:
    if row_version_constraint is None or requested_version_constraint is None:
        return True
    return row_version_constraint == requested_version_constraint


def _build_resolved(row: Any) -> NormalizedCommandResolved:
    return NormalizedCommandResolved(
        normalized_command_id=row.normalized_command_id,
        template_string=str(row.template_string),
        output_parser=(str(row.output_parser) if row.output_parser else None),
        timeout_ms=int(row.timeout_ms),
        requires_privileged=bool(row.requires_privileged),
    )


# Rendering do comando
def _render_command(
    *,
    template_string: str,
    snapshot: dict[str, Any],
    command_vars: dict[str, Any],
) -> str:
    """Renderiza template_string via str.format_map."""
    context: dict[str, Any] = {}
    context.update(command_vars)
    context.update(snapshot)
    try:
        return template_string.format_map(context)
    except KeyError as exc:
        raise _ValidationFailure(f"template referencia variável ausente: {exc!s}") from exc


# Marcadores de status intermediários
def _mark_running(order_id: UUID) -> None:
    """Transição validating -> running (start real do SSH)."""
    with session_scope() as db:
        db.execute(
            text(
                """
                UPDATE provisioning_order
                SET status = CAST('running' AS provisioning_status_enum)
                WHERE provisioning_order_id = :id
                AND status = CAST('validating' AS provisioning_status_enum)
                """
            ),
            {"id": str(order_id)},
        )


# Fase 3
@dataclass(frozen=True, slots=True)
class _PersistOutcome:
    needs_rollback: bool
    successful_step_orders: list[int]
    failure_reason: str | None
    final_status_if_no_rollback: ProvisioningStatus


def _phase_persist_results(
    *,
    ctx: _LoadedContext,
    result: ProvisioningResult,
) -> _PersistOutcome:
    """Grava um provisioning_step por StepResult do adapter."""
    successful_orders: list[int] = []
    failed_steps: list[tuple[int, str]] = []  # (step_order, step_key)

    with session_scope() as db:
        for idx, step_result in enumerate(result.steps or [], start=1):
            step_key = ctx.step_key_by_order.get(idx) or f"__pos_{idx}__"
            db.add(
                ProvisioningStep(
                    provisioning_order_id=ctx.order_id,
                    step_order=idx,
                    step_key=step_key,
                    phase=StepPhase.EXECUTION.value,
                    command_sent=_truncate(step_result.command_sent),
                    output_received=_truncate(step_result.output_received),
                    parser_output=dict(step_result.parser_output or {}) or None,
                    success=bool(step_result.success),
                    duration_ms=(
                        int(step_result.duration_ms)
                        if step_result.duration_ms is not None
                        else None
                    ),
                )
            )
            if step_result.success:
                successful_orders.append(idx)
            else:
                failed_steps.append((idx, step_key))
        db.flush()

    if not failed_steps:
        return _PersistOutcome(
            needs_rollback=False,
            successful_step_orders=successful_orders,
            failure_reason=None,
            final_status_if_no_rollback=ProvisioningStatus.SUCCESS,
        )

    # Há falhas: decide rollback baseando-se no rollback_map.
    rollback_covers_failure = any(
        step_key in ctx.rollback_command_keys for _, step_key in failed_steps
    )
    failure_reason = "step(s) falharam: " + ", ".join(f"#{idx} ({sk})" for idx, sk in failed_steps)
    if rollback_covers_failure:
        return _PersistOutcome(
            needs_rollback=True,
            successful_step_orders=successful_orders,
            failure_reason=failure_reason,
            final_status_if_no_rollback=ProvisioningStatus.FAILED,  # unused
        )

    # fail_policy=continue implícito (rollback_map não cobre): PARTIAL.
    return _PersistOutcome(
        needs_rollback=False,
        successful_step_orders=successful_orders,
        failure_reason=failure_reason,
        final_status_if_no_rollback=(
            ProvisioningStatus.PARTIAL if successful_orders else ProvisioningStatus.FAILED
        ),
    )


# Fase 4: rollback
def _phase_rollback(*, ctx: _LoadedContext, outcome: _PersistOutcome) -> None:
    """Executa rollback dos steps bem-sucedidos em ordem REVERSA."""
    # Reconstrói lista de PlannedCommand na ordem reversa dos sucessos.
    reversed_orders = list(reversed(outcome.successful_step_orders))
    planned_rollback: list[PlannedCommand] = []
    unresolved: list[str] = []

    # Segunda TX curta para resolver comandos de rollback (queries via cache).
    with session_scope() as db:
        # Reconsulta a ordem para pegar snapshot + template atuais.
        order = db.get(ProvisioningOrder, ctx.order_id)
        if order is None:  # invariante violada; loga e desiste.
            log.error(
                "provisioning.worker.rollback_order_not_found",
                provisioning_order_id=str(ctx.order_id),
            )
            _mark_failed(ctx.order_id, "rollback: order desapareceu")
            return
        template = _load_active_template(db, order.provisioning_template_id)
        olt_model_id = _load_olt_model_id(db, _get_olt_model_id_for_olt(db, ctx.olt_id))
        raw = template.raw_template
        version_constraint = raw.get("version_constraint")

        for step_order in reversed_orders:
            step_key = ctx.step_key_by_order.get(step_order)
            if step_key is None:
                continue
            rollback_command_key = ctx.rollback_command_keys.get(step_key)
            if rollback_command_key is None:
                # Step bem-sucedido sem rollback_command_key: sem-op no
                # rollback. Registra para auditoria mas não bloqueia.
                continue
            resolved = _resolve_normalized_command(
                db,
                manufacturer_id=template.manufacturer_id,
                olt_model_id=olt_model_id,
                command_key=rollback_command_key,
                version_constraint=version_constraint,
            )
            if resolved is None:
                unresolved.append(rollback_command_key)
                continue
            rendered = _render_command(
                template_string=resolved.template_string,
                snapshot=dict(order.snapshot_params or {}),
                command_vars=dict(template.command_vars or {}),
            )
            planned_rollback.append(
                PlannedCommand(
                    command_key=rollback_command_key,
                    rendered=rendered,
                    timeout_ms=int(resolved.timeout_ms),
                )
            )

    if unresolved:
        # Rollback comprometido antes de tocar OLT: registra e marca FAILED.
        reason = (
            outcome.failure_reason or ""
        ) + f" | rollback abortado: comandos não resolvidos {unresolved}"
        _persist_rollback_row(
            order_id=ctx.order_id,
            reason=reason,
            rollback_commands=[],
            status=RollbackStatus.FAILED,
            output_received=None,
            executed=False,
        )
        _mark_failed(ctx.order_id, reason)
        return

    if not planned_rollback:
        _persist_rollback_row(
            order_id=ctx.order_id,
            reason=outcome.failure_reason or "step(s) falharam",
            rollback_commands=[],
            status=RollbackStatus.SUCCESS,  # no-op success
            output_received=None,
            executed=False,
        )
        _mark_failed(ctx.order_id, outcome.failure_reason or "step falhou sem rollback")
        return

    # Chama adapter para executar rollback. Factory decide pelo
    rollback_plan = ProvisioningPlan(locator=ctx.locator, commands=planned_rollback)
    adapter = get_olt_adapter(manufacturer_slug=ctx.manufacturer_slug)
    try:
        rollback_result = adapter.deprovision_onu(
            ctx.connection_config,
            rollback_plan,
            olt_id=ctx.olt_id,
        )
    except Exception as exc:
        log.exception(
            "provisioning.worker.rollback_adapter_failed",
            provisioning_order_id=str(ctx.order_id),
            manufacturer_slug=ctx.manufacturer_slug,
            error=str(exc),
        )
        _persist_rollback_row(
            order_id=ctx.order_id,
            reason=(outcome.failure_reason or "") + f" | rollback adapter: {exc}",
            rollback_commands=[],
            status=RollbackStatus.FAILED,
            output_received=None,
            executed=True,
        )
        _mark_failed(
            ctx.order_id,
            f"rollback adapter falhou: {exc}",
        )
        return

    # Grava rollback + finaliza status.
    rollback_commands = _pack_rollback_commands(planned_rollback, rollback_result.steps or [])
    all_ok = all(s.success for s in (rollback_result.steps or []))
    combined_output = (
        "\n---\n".join(
            (s.output_received or "") for s in (rollback_result.steps or []) if s.output_received
        )
        or None
    )

    _persist_rollback_row(
        order_id=ctx.order_id,
        reason=outcome.failure_reason or "rollback executed",
        rollback_commands=rollback_commands,
        status=(RollbackStatus.SUCCESS if all_ok else RollbackStatus.FAILED),
        output_received=_truncate(combined_output),
        executed=True,
    )

    if all_ok:
        _mark_finished(
            ctx.order_id,
            ProvisioningStatus.ROLLED_BACK,
            failure_reason=outcome.failure_reason,
        )
    else:
        _mark_failed(
            ctx.order_id,
            f"rollback falhou parcialmente. {outcome.failure_reason or ''}".strip(),
        )


def _pack_rollback_commands(
    planned: list[PlannedCommand],
    steps: list[StepResult],
) -> list[dict[str, Any]]:
    """Serializa list[StepResult] no shape do JSONB rollback_commands"""
    out: list[dict[str, Any]] = []
    for i, s in enumerate(steps):
        step_key = planned[i].command_key if i < len(planned) else f"__pos_{i}__"
        out.append(
            {
                "step_key": step_key,
                "command_sent": _truncate(s.command_sent),
                "output_received": _truncate(s.output_received),
                "success": bool(s.success),
                "duration_ms": (int(s.duration_ms) if s.duration_ms is not None else None),
            }
        )
    return out


def _persist_rollback_row(
    *,
    order_id: UUID,
    reason: str,
    rollback_commands: list[dict[str, Any]],
    status: RollbackStatus,
    output_received: str | None,
    executed: bool,
) -> None:
    with session_scope() as db:
        db.add(
            ProvisioningRollback(
                provisioning_order_id=order_id,
                reason=reason[:1000],
                rollback_commands=rollback_commands,
                rollback_status=status,
                output_received=output_received,
                executed=executed,
                executed_at=_utcnow() if executed else None,
            )
        )
        db.flush()


def _get_olt_model_id_for_olt(db: Session, olt_id: UUID) -> UUID | None:
    """Reconsulta olt_model_id via olt.olt_id (evita lazy-load na fase 4)."""
    row = db.execute(
        text("SELECT olt_model_id FROM olt WHERE olt_id = :id"),
        {"id": str(olt_id)},
    ).first()
    return row[0] if row else None


# Finalização sem rollback
def _finalize(order_id: UUID, outcome: _PersistOutcome) -> None:
    _mark_finished(
        order_id,
        outcome.final_status_if_no_rollback,
        failure_reason=outcome.failure_reason,
    )
    if outcome.final_status_if_no_rollback == ProvisioningStatus.SUCCESS:
        _try_materialize_onu(order_id)
    log.info(
        "provisioning.worker.finished",
        provisioning_order_id=str(order_id),
        status=outcome.final_status_if_no_rollback.value,
        successful_steps=len(outcome.successful_step_orders),
    )


def _mark_failed(order_id: UUID, error_message: str) -> None:
    """Melhor esforço: se a própria escrita falhar, apenas loga."""
    try:
        with session_scope() as db:
            db.execute(
                text(
                    """
                    UPDATE provisioning_order
                    SET status = CAST('failed' AS provisioning_status_enum),
                        finished_at = NOW(),
                        failure_reason = :err
                    WHERE provisioning_order_id = :id
                    """
                ),
                {"err": error_message[:1000], "id": str(order_id)},
            )
    except Exception as exc:
        log.exception(
            "provisioning.worker.mark_failed_failed",
            provisioning_order_id=str(order_id),
            error=str(exc),
        )


def _mark_finished(
    order_id: UUID,
    status: ProvisioningStatus,
    *,
    failure_reason: str | None,
) -> None:
    with session_scope() as db:
        db.execute(
            text(
                """
                UPDATE provisioning_order
                SET status = CAST(:status AS provisioning_status_enum),
                    finished_at = NOW(),
                    failure_reason = :err
                WHERE provisioning_order_id = :id
                """
            ),
            {
                "status": status.value,
                "err": (failure_reason[:1000] if failure_reason else None),
                "id": str(order_id),
            },
        )


# Materialização de ONU pós-SUCCESS (Rodada 3, P-M18d.1)
def _try_materialize_onu(order_id: UUID) -> None:
    """Cria linha `onu` a partir de `pending_onu` quando SUCCESS."""
    try:
        with session_scope() as db:
            row = db.execute(
                text(
                    """
                    SELECT olt_id, pon_port_id, provisioning_template_id,
                            onu_id, snapshot_params
                    FROM provisioning_order
                    WHERE provisioning_order_id = :id
                    """
                ),
                {"id": str(order_id)},
            ).first()
            if row is None:
                log.error(
                    "provisioning.materialization.order_missing",
                    provisioning_order_id=str(order_id),
                )
                return
            olt_id, pon_port_id, template_id, existing_onu_id, snap = row
            snap = snap or {}
            snap_serial = snap.get("serial")

            # Caso 1: order já apontava para uma onu viva. Só marca a
            # pending_onu correspondente (se houver) como resolvida.
            if existing_onu_id is not None:
                if snap_serial:
                    db.execute(
                        text(
                            """
                            UPDATE pending_onu
                                SET state = CAST('resolved' AS pending_onu_state_enum),
                                    resolution_type = CAST('provisioned' AS resolution_type_enum),
                                    resolved_at = NOW(),
                                    linked_onu_id = :onu_id,
                                    last_seen_at = NOW()
                            WHERE olt_id = :olt AND pon_port_id = :pon
                                AND serial = :serial
                                AND state IN ('detected', 'waiting')
                            """
                        ),
                        {
                            "onu_id": str(existing_onu_id),
                            "olt": str(olt_id),
                            "pon": str(pon_port_id),
                            "serial": snap_serial,
                        },
                    )
                log.info(
                    "provisioning.materialization.pending_resolved_only",
                    provisioning_order_id=str(order_id),
                    onu_id=str(existing_onu_id),
                )
                return

            # Casos 2 e 3: order.onu_id NULL. Busca pending_onu ativa
            # correspondente para pegar onu_model_id (matching Rodada 2).
            if not snap_serial:
                log.warning(
                    "provisioning.materialization.no_serial_in_snapshot",
                    provisioning_order_id=str(order_id),
                )
                return

            pending_row = db.execute(
                text(
                    """
                    SELECT pending_onu_id, onu_model_id
                    FROM pending_onu
                    WHERE olt_id = :olt AND pon_port_id = :pon
                        AND serial = :serial
                        AND state IN ('detected', 'waiting')
                    ORDER BY last_seen_at DESC
                    LIMIT 1
                    FOR UPDATE
                    """
                ),
                {
                    "olt": str(olt_id),
                    "pon": str(pon_port_id),
                    "serial": snap_serial,
                },
            ).first()

            if pending_row is None:
                # Sem pending_onu ativa: nada a materializar (pode ter
                # sido resolvida em paralelo por outro fluxo). Ordem
                # continua SUCCESS.
                log.warning(
                    "provisioning.materialization.pending_not_found",
                    provisioning_order_id=str(order_id),
                    serial=snap_serial,
                )
                return

            pending_id, pending_onu_model_id = pending_row

            if pending_onu_model_id is None:
                # Caso 3: vendor_id não bateu no matching do discovery.
                # Marca pending resolved sem linked_onu_id.
                db.execute(
                    text(
                        """
                        UPDATE pending_onu
                        SET state = CAST('resolved' AS pending_onu_state_enum),
                            resolution_type = CAST('provisioned' AS resolution_type_enum),
                            resolved_at = NOW(),
                            last_seen_at = NOW()
                        WHERE pending_onu_id = :id
                        """
                    ),
                    {"id": str(pending_id)},
                )
                log.warning(
                    "provisioning.materialization.skipped_no_onu_model",
                    provisioning_order_id=str(order_id),
                    pending_onu_id=str(pending_id),
                    serial=snap_serial,
                )
                return

            # Caso 2: cria onu.
            line_profile_id = snap.get("line_profile_id")
            service_profile_id = snap.get("service_profile_id")
            onu_index = snap.get("onu_index")

            new_onu_id = db.execute(
                text(
                    """
                    INSERT INTO onu (
                        onu_model_id, pon_port_id,
                        line_profile_id, service_profile_id,
                        provisioning_template_id, serial, onu_index,
                        provisioned
                    ) VALUES (
                        :model, :pon, :lp, :sp, :tpl, :serial, :idx, TRUE
                    )
                    RETURNING onu_id
                    """
                ),
                {
                    "model": str(pending_onu_model_id),
                    "pon": str(pon_port_id),
                    "lp": str(line_profile_id) if line_profile_id else None,
                    "sp": str(service_profile_id) if service_profile_id else None,
                    "tpl": str(template_id),
                    "serial": snap_serial,
                    "idx": onu_index,
                },
            ).scalar_one()

            # Amarra order + pending_onu à nova onu.
            db.execute(
                text(
                    """
                    UPDATE provisioning_order
                    SET onu_id = :onu
                    WHERE provisioning_order_id = :id
                    """
                ),
                {"onu": str(new_onu_id), "id": str(order_id)},
            )
            db.execute(
                text(
                    """
                    UPDATE pending_onu
                    SET state = CAST('resolved' AS pending_onu_state_enum),
                        resolution_type = CAST('provisioned' AS resolution_type_enum),
                        resolved_at = NOW(),
                        linked_onu_id = :onu,
                        last_seen_at = NOW()
                    WHERE pending_onu_id = :pid
                    """
                ),
                {"onu": str(new_onu_id), "pid": str(pending_id)},
            )

            log.info(
                "provisioning.materialization.success",
                provisioning_order_id=str(order_id),
                onu_id=str(new_onu_id),
                serial=snap_serial,
                onu_model_id=str(pending_onu_model_id),
            )
    except Exception as exc:
        log.exception(
            "provisioning.materialization.failed",
            provisioning_order_id=str(order_id),
            error=str(exc),
        )
