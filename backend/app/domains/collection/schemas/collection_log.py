# Schema Pydantic v2 de CollectionLog.

# Apenas Read: o cliente não cria nem altera logs.
# Só o worker (via session sync) escreve no contexto de um collection_job.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CollectionLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    collection_log_id: UUID
    collection_job_id: UUID
    olt_id: UUID
    step_name: str | None
    command_sent: str
    output_received: str | None
    parser_status: str | None
    success: bool
    duration_ms: int | None
    executed_at: datetime
