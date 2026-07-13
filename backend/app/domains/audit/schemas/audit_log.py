# Schemas de leitura do audit_log

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditLogRead(BaseModel):
    """Payload de leitura de um registro de auditoria."""

    audit_log_id: UUID
    app_user_id: UUID | None = None
    olt_id: UUID | None = None
    onu_id: UUID | None = None
    provisioning_order_id: UUID | None = None

    entity_type: str
    entity_id: UUID

    action: str
    result: str

    error_detail: str | None = None

    before_data: dict[str, Any] | None = None
    after_data: dict[str, Any] | None = None
    event_metadata: dict[str, Any] | None = None

    request_id: str | None = None

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
