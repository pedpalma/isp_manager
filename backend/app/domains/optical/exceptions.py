# Exceções do domínio Optical

from __future__ import annotations

from uuid import UUID

from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    NotFoundError,
    ValidationError,
)


class OpticalThresholdPolicyNotFound(NotFoundError):
    def __init__(self, policy_id: UUID) -> None:
        super().__init__(
            f"Política de threshold óptico não encontrada: {policy_id}.",
            details={"optical_threshold_policy_id": str(policy_id)},
        )


class OpticalThresholdPolicyConflict(ConflictError):
    def __init__(self, scope_type: str, scope_id: UUID | None, metric_name: str) -> None:
        super().__init__(
            (
                f"Já existe uma política ativa para o escopo {scope_type}"
                f" (scope_id{scope_id}) na métrica {metric_name}."
            ),
            details={
                "scope_type": scope_type,
                "scope_id": str(scope_id) if scope_id is not None else None,
                "metric_name": metric_name,
            },
        )


class OpticalAlertEventNotFound(NotFoundError):
    def __init__(self, alert_id: UUID) -> None:
        super().__init__(
            f"Evento de alerta óptico não encontrado: {alert_id}.",
            details={"optical_alert_event_id": str(alert_id)},
        )


class OpticalAlertInvalidTransition(BadRequestError):
    """Tentativa de transição inválida no ciclo open -> acknowledged -> resolved."""

    def __init__(self, alert_id: UUID, current_status: str, requested_status: str) -> None:
        super().__init__(
            (
                f"Transição inválida de '{current_status}' para '{requested_status}'"
                f" no alerta {alert_id}."
            ),
            details={
                "optical_alert_event_id": str(alert_id),
                "current_status": current_status,
                "requested_status": requested_status,
            },
        )


class OpticalMetricInvalid(ValidationError):
    """Metric_name fora do conjunto SUPPORTED_OPTICAL_METRICS."""

    def __init__(self, metric_name: str) -> None:
        super().__init__(
            f"Métrica óptica inválida: {metric_name!r}.",
            details={"metric_name": metric_name},
        )


class OpticalScopeMismatch(BadRequestError):
    """scope_id obrigatório para escopo != 'global' ou enviado para 'global'."""

    def __init__(self, scope_type: str, has_scope_id: bool) -> None:
        msg = (
            "Escopo 'global' não admite scope_id."
            if scope_type == "global" and has_scope_id
            else f"Escopo '{scope_type}' exige scope_id."
        )
        super().__init__(
            msg,
            details={"scope_type": scope_type, "scope_id_provided": has_scope_id},
        )


class OnuReferenceInvalid(BadRequestError):
    """Reuso do padrão OltReferenceInvalid: FK aponta para entidade ausente ou inativa."""

    def __init__(self, onu_id: UUID) -> None:
        super().__init__(
            f"ONU não encontrada ou desativada: {onu_id}.",
            details={"onu_id": str(onu_id)},
        )
