# Rota de diagnóstico
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.logging import get_logger
from app.tasks.health import ping

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])
log = get_logger(__name__)


class EnqueueResponse(BaseModel):
    task_id: str
    status: Literal["queued"] = "queued"


@router.post(
    "/echo-task",
    response_model=EnqueueResponse,
    summary="Enfileira a task ping (teste de correlação API↔worker)",
    description=(
        "Dispara a task `ping` no Celery e devolve o id da task. "
        "Use para confirmar que os logs da API e do worker compartilham o "
        "mesmo request_id: `docker compose logs api worker | jq`."
    ),
)
async def echo_task() -> EnqueueResponse:
    # Leva o request_id do request atual
    log.info("diagnostics.echo_task.enqueue")
    # .delay() dispara before_task_publish, que injeta o request_id no header
    async_result = ping.delay()
    log.info("diagnostics.echo_task.enqueued", task_id=async_result.id)
    return EnqueueResponse(task_id=async_result.id)
