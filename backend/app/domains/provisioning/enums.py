# Enums do domínio provisioning

from __future__ import annotations

from enum import Enum


class TemplateScope(str, Enum):  # noqa: UP042
    """Escopo declarado de provisioning_template."""

    ONU_PROVISION = "onu_provision"
    ONU_REMOVE = "onu_remove"
    VLAN_CONFIG = "vlan_config"


class TemplateStepPhase(str, Enum):  # noqa: UP042
    """Fase de execução de um step dentro do raw_template
    EXECUTE: Comando que altera o estado da OLT.
    VERIFY: Comando de leitura para confirmar estado após execução"""

    EXECUTE = "execute"
    VERIFY = "verify"


class TemplateStepFailPolicy(str, Enum):  # noqa: UP042
    """Política de falha de um step.
    ABORT: falha do step aborta a order e dispara rollback dos steps anteriores.
    DEGRADE_TO_PARTIAL: Falha do step não aborta, mas order finaliza como partial"""

    ABORT = "abort"
    DEGRADE_TO_PARTIAL = "degrade_to_partial"


class NormalizedCommandType(str, Enum):  # noqa: UP042
    """Categoria semântica de normalized_command"""

    READ = " read"
    PROVISION = "provision"
    DEPROVISION = " deprovision"
    CONFIG = "config"


class ProvisioningStatus(str, Enum):  # noqa: UP042
    """Estados de provisioning_order."""

    PENDING = "pending"
    VALIDATING = "validating"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    PARTIAL = "partial"


class RollBackStatus(str, Enum):  # noqa: UP042
    """Status  de provisioning_rollback."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class StepPhase(str, Enum):  # noqa: UP042
    """Fases de execução."""

    VALIDATION = "validation"
    EXECUTION = "execution"
    VERIFY = "verify"


# Estados considerados "ativos" para bloquear uma nova ordem sobre a mesma ONU.
ACTIVE_PROVISIONING_STATUSES: frozenset[ProvisioningStatus] = frozenset(
    {
        ProvisioningStatus.PENDING,
        ProvisioningStatus.VALIDATING,
        ProvisioningStatus.RUNNING,
    }
)

# Estados terminais. Serve como sanity check no worker.
TERMINAL_PROVISIONING_STATUSES: frozenset[ProvisioningStatus] = frozenset(
    {
        ProvisioningStatus.SUCCESS,
        ProvisioningStatus.FAILED,
        ProvisioningStatus.ROLLED_BACK,
        ProvisioningStatus.PARTIAL,
    }
)
