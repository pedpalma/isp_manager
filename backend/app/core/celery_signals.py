# Sinais do Celery: correlação de logs e configuração de logging do worker.

# Fluxo do request_id:
#   1. A API recebe um request; o RequestIDMiddleware amarra o request_id no
#      contexto (structlog.contextvars).
#   2. A rota chama ping.delay(). before_task_publish lê o request_id do
#      contexto e o anexa nos HEADERS da mensagem Celery.
#   3. No worker, task_prerun lê o request_id do header e o amarra no contexto
#      do processo do worker.
#   4. Tudo que o worker logar durante a task sai com o MESMO request_id.
#   5. task_postrun limpa o contexto para o id não vazar para a próxima task.

from __future__ import annotations

from typing import Any

from celery.signals import (
    before_task_publish,
    setup_logging,
    task_postrun,
    task_prerun,
)

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
    """Conectar a setup_logging faz o Celery NÃO instalar o logging próprio dele,
    deixando o nosso structlog no comando dentro do worker."""
    configure_logging()


@before_task_publish.connect
def _inject_request_id(headers: dict[str, Any] | None = None, **_kwargs: Any) -> None:
    """Lado API: anexa o request_id corrente nos headers da task.
    Com o protocolo v2 do Celery (padrão), chaves em `headers` viram atributos
    de `task.request` no worker."""
    request_id = get_request_id()
    if request_id and headers is not None:
        headers[REQUEST_ID_KEY] = request_id


@task_prerun.connect
def _bind_request_id(task: Any = None, **_kwargs: Any) -> None:
    """Lado worker: recupera o request_id do header e injeta no contexto de log."""
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
    """Lado worker: loga o fim e limpa o contexto (evita vazamento entre tasks)."""
    log.info(
        "task.finish",
        task_name=getattr(task, "name", None),
        task_id=getattr(getattr(task, "request", None), "id", None),
    )
    clear_request_context()
