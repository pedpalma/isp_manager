# Schemas Pydantic v2 de ProvisioningOrder (M18d).
#
# Três shapes:
#   ProvisioningOrderCreate  = POST body
#   ProvisioningOrderRead    = leitura lean (lista paginada; sem steps/rollback)
#   ProvisioningOrderDetailRead = Read + steps (embed 1:N) + rollback (satellite opcional)
#
# Padrão embed 1:N segue CollectionJobDetailRead (M16).
# Rollback é 0 ou 1 por ordem (mesma linha por ordem, JSONB agregado no DDL).

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domains.provisioning.enums import ProvisioningStatus
from app.domains.provisioning.schemas.provisioning_rollback import (
    ProvisioningRollbackRead,
)
from app.domains.provisioning.schemas.provisioning_step import ProvisioningStepRead
from app.domains.provisioning.schemas.snapshot_params import SnapshotParams


class ProvisioningOrderCreate(BaseModel):
    """Payload de POST /provisioning-orders."""

    model_config = ConfigDict(extra="forbid")

    olt_id: UUID
    pon_port_id: UUID
    serial: str = Field(min_length=1, max_length=64)
    provisioning_template_id: UUID
    idempotency_key: str = Field(min_length=1, max_length=128)
    retry_of_order_id: UUID | None = None
    snapshot: SnapshotParams


class ProvisioningOrderRead(BaseModel):
    """Leitura lean da ordem (lista paginada; sem steps/rollback)."""

    model_config = ConfigDict(from_attributes=True)

    provisioning_order_id: UUID
    olt_id: UUID
    pon_port_id: UUID
    onu_id: UUID | None
    app_user_id: UUID
    provisioning_template_id: UUID
    retry_of_order_id: UUID | None
    idempotency_key: str
    status: ProvisioningStatus
    failure_reason: str | None
    result_summary: str | None
    snapshot_params: dict[str, Any]
    requested_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class ProvisioningOrderDetailRead(ProvisioningOrderRead):
    """Detalhe da ordem com steps (embed 1:N) e rollback (0 ou 1)."""

    steps: list[ProvisioningStepRead]
    rollback: ProvisioningRollbackRead | None
