# Schemas Pydantic v2 de CollectionJob.

# Padrão seguido: Topology (1:N) para o detalhe com logs embutidos.
# CollectionJobRead é "lean" (sem logs) para a lista paginada;
# CollectionJobDetailRead estende e carrega logs como list[CollectionLogRead].

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domains.collection.enums import JobStatus, JobTriggerType
from app.domains.collection.schemas.collection_log import CollectionLogRead


class CollectionJobCreate(BaseModel):
    """Payload de POST /collection-jobs.

    job_type fixado em "discovery" pelo service.
    Não é exposto job_type no payload para não deixar
    o cliente acionar tipos futuros por engano."""

    olt_id: UUID


class CollectionJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    collection_job_id: UUID
    olt_id: UUID
    requested_by_user_id: UUID | None
    job_type: str
    trigger_type: JobTriggerType
    target_scope: str | None
    payload: dict[str, Any] | None
    status: JobStatus
    retry_count: int
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None
    created_at: datetime


class CollectionJobDetailRead(CollectionJobRead):
    """CollectionJobRead estendido com os logs daquele job.

    Embed 1:N segue padrão TopologyService (queries separadas + montagem
    em Python), NÃO o padrão1:1 com onu_runtime_state."""

    logs: list[CollectionLogRead]
