# Configuração central de logging estruturado (structlog).

from __future__ import annotations

import logging
import sys

import structlog

from app.core.config import settings

# Chave usada para correlação de requests entre API e worker.
REQUEST_ID_KEY = "request_id"


def configure_logging() -> None:
    """Configura structlog + stdlib logging. Idempotente o suficiente para ser
    chamada no startup da API e do worker."""
    level = logging.getLevelName(settings.logging.log_level)
    use_json = settings.logging.log_format == "json"

    # Cadeia de processadores compartilhada entre logs nativos do structlog e
    # logs "estrangeiros" (stdlib: uvicorn, sqlalchemy, etc.).
    pre_chain: list[structlog.types.Processor] = [
        # Injeta o que estiver no contexto (request_id) em toda linha.
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        # Timestamp ISO-8601 em UTC (convenção do projeto: UTC no banco e nos logs).
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer()
        if use_json
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    # structlog nativo: aplica a pre_chain e entrega ao ProcessorFormatter da stdlib.
    structlog.configure(
        processors=[*pre_chain, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )

    # Formatter único usado pelo handler raiz da stdlib. `foreign_pre_chain`
    # aplica a mesma cadeia aos logs que NÃO vieram do structlog.
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=pre_chain,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Fail-fast: valida o formatter antes de instalá-lo no root.
    _self_test(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # uvicorn.access é barulhento e tem formato próprio: silenciamos o handler
    # dele porque o nosso LoggingMiddleware já loga cada request com mais contexto.
    access = logging.getLogger("uvicorn.access")
    access.handlers.clear()
    access.propagate = False

    # Garante que uvicorn.error e sqlalchemy propaguem para o nosso handler raiz.
    for name in ("uvicorn", "uvicorn.error", "sqlalchemy.engine", "celery"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True


def _self_test(formatter: logging.Formatter) -> None:
    """Fail-fast: empurra um registro sintético pelo formatter para garantir que
    a configuração está sã ANTES de a aplicação subir."""
    record = logging.LogRecord(
        name="app.logging.selftest",
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg="logging selftest",
        args=(),
        exc_info=None,
    )
    try:
        rendered = formatter.format(record)
    except Exception as exc:  # noqa: BLE001 - converter em mensagem acionável
        raise RuntimeError(
            "Falha ao configurar o logging: o ProcessorFormatter não conseguiu "
            "renderizar um registro. Causa comum: 'processors=[pre_chain, ...]' "
            "(lista aninhada) em vez de 'processors=[*pre_chain, ...]'. "
            f"Erro original: {exc!r}"
        ) from exc
    if not isinstance(rendered, str):
        raise RuntimeError(
            "Logging mal configurado: o último processor do ProcessorFormatter "
            "deve devolver str (use JSONRenderer/ConsoleRenderer por último)."
        )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Retorna um logger estruturado. Use o `__name__` do módulo como nome."""
    return structlog.stdlib.get_logger(name)


# Helpers de contexto de request (correlação de logs).
def bind_request_id(request_id: str) -> None:
    """Amarra o request_id ao contexto atual (task/coroutine/thread)."""
    structlog.contextvars.bind_contextvars(**{REQUEST_ID_KEY: request_id})


def get_request_id() -> str | None:
    """Lê o request_id do contexto atual, se houver."""
    value = structlog.contextvars.get_contextvars().get(REQUEST_ID_KEY)
    return value if isinstance(value, str) else None


def clear_request_context() -> None:
    """Limpa todo o contexto. Chamar ao fim de um request/task para não vazar
    o request_id para o próximo trabalho no mesmo processo."""
    structlog.contextvars.clear_contextvars()
