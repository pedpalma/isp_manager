# Schemas de optical_reading.
# Apenas Read: leituras são geradas pelo worker do signal_reading;
# não há Create/Update via API (somente leitura externa).

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class OpticalReadingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    optical_reading_id: UUID
    onu_id: UUID
    rx_power_dbm: float | None
    tx_power_dbm: float | None
    status: str | None
    alert_critical: bool
    distance_m: float | None
    temperature: float | None
    voltage: float | None
    bias_current: float | None
    collected_at: datetime
    collection_source: str | None
