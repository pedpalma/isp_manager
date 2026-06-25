# Reexports dos schemas para imports curtos.
from __future__ import annotations

from app.domains.optical.schemas.effective_thresholds import (
    EffectiveThreshold,
    EffectiveThresholdsRead,
)
from app.domains.optical.schemas.optical_alert_event import (
    OpticalAlertEventRead,
)
from app.domains.optical.schemas.optical_reading import OpticalReadingRead
from app.domains.optical.schemas.optical_threshold_policy import (
    OpticalThresholdPolicyCreate,
    OpticalThresholdPolicyRead,
    OpticalThresholdPolicyUpdate,
)

__all__ = [
    "EffectiveThreshold",
    "EffectiveThresholdsRead",
    "OpticalAlertEventRead",
    "OpticalReadingRead",
    "OpticalThresholdPolicyCreate",
    "OpticalThresholdPolicyRead",
    "OpticalThresholdPolicyUpdate",
]
