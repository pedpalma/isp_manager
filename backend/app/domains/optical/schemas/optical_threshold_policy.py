# Schemas de optical_threshold_policy.
# scope_type e metric_name são IMUTÁVEIS.
# Update permite mudar thresholds, severity e active.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domains.optical.enums import OpticalScopeType, OpticalSeverity


class OpticalThresholdPolicyCreate(BaseModel):
    scope_type: OpticalScopeType
    # scope_id obrigatório quando scope_type != 'global'; service válida.
    scope_id: UUID | None = None
    metric_name: str = Field(min_length=1, max_length=64)
    threshold_min: float | None = None
    threshold_max: float | None = None
    severity: OpticalSeverity = OpticalSeverity.WARNING
    active: bool = True


class OpticalThresholdPolicyUpdate(BaseModel):
    # scope_type, scope_id e metric_name são IMUTÁVEIS.
    # Para mudar par chave, desative a antiga e crie nova.
    threshold_min: float | None = None
    threshold_max: float | None = None
    severity: OpticalSeverity | None = None
    active: bool | None = None


class OpticalThresholdPolicyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    optical_threshold_policy_id: UUID
    scope_type: OpticalScopeType
    scope_id: UUID | None
    metric_name: str
    threshold_min: float | None
    threshold_max: float | None
    severity: OpticalSeverity
    active: bool
    created_at: datetime
    updated_at: datetime
