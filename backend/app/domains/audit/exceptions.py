# Exceções do domínio de auditoria

from __future__ import annotations

from uuid import UUID

from app.core.exceptions import NotFoundError


class AuditLogNotFound(NotFoundError):
    """404 quando o registro de auditoria pedido não existir."""

    def __init__(self, audit_log_id: UUID) -> None:
        super().__init__(
            f"Registro de auditoria não encontrado: {audit_log_id}.",
            details={"audit_log_id": str(audit_log_id)},
        )
