# Config de logs estruturados
from __future__ import annotations

import logging
import sys

import structlog

from app.core.config import settings

# Chave de correlação entre requests API e Worker
REQUEST_ID_KEY = "request_id"


def configure_logging() -> None:
    # Função idempotente que configura structured logs
    level = logging.getLevelName(settings.logging.log_level)
    use_json = settings.logging.log_format("json")

    # Cadeia de processadores compartilhados entre logs
    pre_chain: list[structlog.types.Processor] = [
        # Injeta o contexto
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        # Timestamp
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer()
        if use_json
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    # Structlog nativo
    structlog.configure(
        processors=[*pre_chain, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )

    # Formatter único usado pelo handler raiz da stdlib.
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=pre_chain,
        processor=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Silenciando o logger o uvicorn
    access = logging.getLogger("uvicorn.access")
    access.handlers.clear()
    access.propagate = False

    # Garante que o uvicorn e o sqlalchemy propaguem os erros para o handler raiz.
    for name in ("uvicorn", "uvicorn.error", "sqlalchemy.engine", "celery"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    # Retorna um logger estruturado
    return structlog.stdlib.get_logger(name)


# Helpers de contexto
def bind_request_id(request_id: str) -> None:
    # Amarra o request_id ao contexto atual
    structlog.contextvars.bind_contextvars(**{REQUEST_ID_KEY: request_id})


def get_request_id() -> str | None:
    # Lê o request_id caso exista
    value = structlog.contextvars.get_contextvars().get(REQUEST_ID_KEY)
    return value if isinstance(value, str) else None


def clear_request_context() -> None:
    # Limpa o contexto para não vazar
    structlog.contextvars.clear_contextvars()
