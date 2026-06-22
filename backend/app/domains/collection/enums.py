# Enums do domínio collection.

# Espelham os tipos nativos do Postgres declarados no 0001_initial.sql.
# Cada valor Python é copia EXATA do rótulo do CREATE TYPE, incluindo case.

from __future__ import annotations

from enum import Enum


class JobStatus(str, Enum):  # noqa: UP042
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"


class JobTriggerType(str, Enum):  # noqa: UP042
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    RETRY = "retry"
    WEBHOOK = "webhook"


class PendingOnuState(str, Enum):  # noqa: UP042
    DETECTED = "detected"
    WAITING = "waiting"
    RESOLVED = "resolved"


class ResolutionType(str, Enum):  # noqa: UP042
    PROVISIONED = "provisioned"
    IGNORED = "ignored"
    DUPLICATE = "duplicate"
    REJECTED = "rejected"
    MERGED = "merged"


# Constantes de job_type (coluna TEXT no DDL, não enum nativo).
# São "soft constants" para evitar string mágica espalhada.
JOB_TYPE_DISCOVERY = "discovery"

# Conjunto de status terminais. Útil para barrar transições inválidas.
TERMINAL_JOB_STATUS = frozenset(
    {
        JobStatus.SUCCESS,
        JobStatus.FAILED,
        JobStatus.PARTIAL,
        JobStatus.CANCELLED,
    }
)

# Status "vivos" do job. Espelha o predicado do índice uq_collection_job_running.
RUNNING_JOB_STATUS = frozenset(
    {
        JobStatus.PENDING,
        JobStatus.RUNNING,
    }
)
