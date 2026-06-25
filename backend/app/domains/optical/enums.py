# Adiciona os enums do domínio óptico

from __future__ import annotations

from enum import Enum


class OpticalAlertStatus(str, Enum):  # noqa: UP042
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class OpticalSeverity(str, Enum):  # noqa: UP042
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class OpticalScopeType(str, Enum):  # noqa: UP042
    ONU = "onu"
    PON_PORT = "pon_port"
    OLT = "olt"
    GLOBAL = "global"


# Espelha a coluna optical_reading, que admite politica de threshold
SUPPORTED_OPTICAL_METRICS = frozenset(
    {
        "rx_power_dbm",
        "tx_power_dbm",
        "temperature",
        "voltage",
        "bias_current",
        "distance_m",
    }
)

# Ordem de prioridade na resolução hierárquica.
SCOPE_PRIORITY_ORDER = list[OpticalScopeType] = [  # pyright: ignore[reportGeneralTypeIssues]
    OpticalScopeType.ONU,
    OpticalScopeType.PON_PORT,
    OpticalScopeType.OLT,
    OpticalScopeType.GLOBAL,
]

JOB_TYPE_SIGNAL_READING = "signal_reading"
