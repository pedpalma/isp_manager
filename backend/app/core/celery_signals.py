# Sinais Celery, faz a correlação dos logs e configura o logging do worker.
from __future__ import annotations

from typing import Any

from celery.signals import before_task_publish, setup_logging, task_postrun, task_prerun

from app.core.logging import (
    REQUEST_ID_KEY,
    bind_request_id,
    clear_request_context,
    configure_logging,
    get_logger,
    get_request_id,
)

log = get_logger(__name__)


@setup_logging.connect
def _configure_worker_logging(**_kwargs: Any) -> None:
    # Força o Celery a usar o logging estruturado.
    configure_logging()


@before_task_publish.connect
def _inject_request_id(headers: dict[str, Any] | None = None, **_kwargs: Any) -> None:
    # Anexa o request_id ao header da task.
    request_id = get_request_id()
    if request_id and headers is not None:
        headers[REQUEST_ID_KEY] = request_id


@task_prerun.connect
def _bind_request_id(task: Any = None, **_kwargs: Any) -> None:
    # Recupera o header e injeta no contexto do log
    request_id = getattr(task.request, REQUEST_ID_KEY, None) if task is not None else None
    if request_id:
        bind_request_id(str(request_id))

    log.info(
        "task.start",
        task_name=getattr(task, "name", None),
        task_id=getattr(getattr(task, "request", None), "id", None),
    )


@task_postrun.connect
def _clear_request_id(task: Any = None, **_kwargs: Any) -> None:
    # Loga o fim o limpa o contexto
    log.info(
        "task.finish",
        task_name=getattr(task, "name", None),
        task_id=getattr(getattr(task, "request", None), "id", None),
    )
    clear_request_context()
