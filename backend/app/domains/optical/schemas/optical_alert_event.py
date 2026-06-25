# Schemas de optical_alert_event.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domains.optical.enums import OpticalAlertStatus


class OpticalAlertEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    optical_alert_event_id: UUID
    onu_id: UUID
    policy_id: UUID
    metric_name: str
    value: float
    status: OpticalAlertStatus
    triggered_at: datetime
    resolved_at: datetime | None
    created_at: datetime
