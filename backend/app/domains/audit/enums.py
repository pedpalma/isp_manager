# Enums do domínio de auditoria

from __future__ import annotations

from enum import Enum


class AuditAction(str, Enum):  # noqa: UP042
    """Ações auditadas"""

    # Inventario
    OLT_SOFT_DELETED = "olt.soft_deleted"

    # Credenciais
    CREDENTIAL_CREATED = "credential.created"
    CREDENTIAL_UPDATED = "credential.updated"

    # Autenticação
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_REFRESH = "auth.refresh"
    AUTH_PASSWORD_CHANGED = "auth.password_changed"

    # Provisionamento
    PROVISIONING_ORDER_CREATED = "provisioning_order.created"
    PROVISIONING_ORDER_CANCELED = "provisioning_order.canceled"
    PROVISIONING_ORDER_STARTED = "provisioning_order.started"
    PROVISIONING_ORDER_FINISHED = "provisioning_order.finished"
    PROVISIONING_ORDER_ROLLED_BACK = "provisioning_order.rolled_back"

    # Alertas ópticos
    OPTICAL_ALERT_ACKNOWLEDGED = "optical_alert.acknowledged"
    OPTICAL_ALERT_RESOLVED = "optical_alert.resolved"

    # Coleta
    COLLECTION_JOB_CREATED = "collection_job.created"
    COLLECTION_JOB_FINISHED = "collection_job.finished"


class AuditResult(str, Enum):  # noqa: UP042
    """Resultado agregado da ação."""

    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
