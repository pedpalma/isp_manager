# Exceções do domínio de collections

# As rotas levantam, o global handler serializa no envelope padrão.

from __future__ import annotations

from uuid import UUID

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError


class CollectionJobNotFound(NotFoundError):
    def __init__(self, job_id: UUID) -> None:
        super().__init__(
            f"Job de coleta não encontrada: {job_id}.",
            details={"collection_job_id": str(job_id)},
        )


class CollectionJobConflict(ConflictError):
    """Já existe job ativo (pending/running) para a mesma OLT e job_type.
    Disparado pela violação do índice uq_collection_job_running (migration 0003).
    Mesmo que o cliente esteja iterando rápido, só cabe um job ativo por olt_id,
    job_type, até ele encerrar."""

    def __init__(self, olt_id: UUID, job_type: str) -> None:
        super().__init__(
            "Já existe job de coleta ativo para essa OLT e job_type.",
            details={"olt_id": str(olt_id), "job_type": job_type},
        )


class PendingOnuNotFound(NotFoundError):
    def __init__(self, pending_onu_id: UUID) -> None:
        super().__init__(
            f"Pending ONU não encontrada: {pending_onu_id}.",
            details={"pending_onu_id": str(pending_onu_id)},
        )


class OltReferenceInvalid(BadRequestError):
    """Reutilizado quando o olt_id informado não existe ou está soft-deleted

    Mesma semântica usada em inventory.OltReferenceInvalid (400).
    É mantido o nome genérico para evitar redundância entre classes."""

    def __init__(self, olt_id: UUID):
        super().__init__(
            f"OLT não encontrada ou inativa: {olt_id}.",
            details={"pending_onu_id": str(olt_id)},
        )
