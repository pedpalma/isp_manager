# Schema de resposta de GET /onus/{onu_id}/effective-thresholds.
# Para cada métrica suportada (rx_power_dbm, tx_power_dbm, etc.),
# devolve qual politica ativa está efetivamente aplicada apos resolução
# hierárquica (onu > pon_port > olt > global). Quando não há política
# para a métrica, o campo do dict aparece como None.

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from app.domains.optical.enums import OpticalScopeType, OpticalSeverity


class EffectiveThreshold(BaseModel):
    """Resultado da resolução para UMA métrica."""

    metric_name: str
    optical_threshold_policy_id: UUID
    scope_type: OpticalScopeType
    scope_id: UUID | None
    threshold_min: float | None
    threshold_max: float | None
    severity: OpticalSeverity


class EffectiveThresholdsRead(BaseModel):
    """Diagnostico completo das politicas aplicadas a uma ONU.
    Dict por métrica; valor None significa que não há policy ativa
    para aquela métrica nem em escopo mais específico nem no global."""

    onu_id: UUID
    thresholds: dict[str, EffectiveThreshold | None]
