# Configuração central de logging estruturado (structlog).

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from app.core.config import settings

# Chave usada para correlação de requests entre API e worker.
REQUEST_ID_KEY = "request_id"


def _build_pre_chain() -> list[structlog.types.Processor]:
    """Cadeia de processadores compartilhada entre logs nativos do structlog
    e logs estrangeiros (uvicorn, sqlalchemy, celery, watchfiles)."""
    return [
        # Injeta o que estiver no contexto
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]


def _build_formatter() -> logging.Formatter:
    """Constrói o processorFormatter usado em todos os caminhos"""
    use_json = settings.logging.log_format == "json"
    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer()
        if use_json
        else structlog.dev.ConsoleRenderer(colors=True)
    )
    return structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=_build_pre_chain(),
        processor=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )


def make_uvicorn_formatter() -> logging.Formatter:
    """Factory chamada pelo dictConfig do uvicorn via sintaxe "()"."""
    return _build_formatter()


def get_uvicorn_log_config() -> dict[str:Any]:
    """Retorna o dictConfig que o uvicorn aplica via --log-config no boot."""
    level = settings.logging.log_level
    return {
        "version": 1,
        # CRÍTICO: NÃO desabilitar loggers já criados. Se for True, qualquer
        # logger instanciado antes do dictConfig rodar (e há vários no uvicorn)
        # fica mudo. Quebra o boot inteiro de forma confusa.
        "disable_existing_loggers": False,
        "formatters": {
            "structlog": {
                # Sintaxe "()" do logging.config: instancia chamando a factory.
                # Tem que ser caminho importável completo.
                "()": "app.core.logging.make_uvicorn_formatter",
            },
        },
        "handlers": {
            "default": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "structlog",
            },
        },
        "loggers": {
            "uvicorn": {
                "level": level,
                "handlers": ["default"],
                "propagate": False,
            },
            "uvicorn.error": {
                "level": level,
                "handlers": ["default"],
                "propagate": False,
            },
            # uvicorn.access: silenciado. Nosso LoggingMiddleware já loga cada
            # request com mais contexto (request_id, duração).
            "uvicorn.access": {
                "level": "WARNING",
                "handlers": [],
                "propagate": False,
            },
            # watchfiles: usado pelo --reload em dev. Em prod (sem --reload),
            # estes loggers ficam ociosos. Propagam para o root para sair em JSON.
            "watchfiles": {"level": "INFO", "handlers": [], "propagate": True},
            "watchfiles.main": {"level": "INFO", "handlers": [], "propagate": True},
            "watchfiles.watcher": {"level": "INFO", "handlers": [], "propagate": True},
        },
        # Root captura todo o resto (sqlalchemy, celery, código do app que
        # eventualmente logue antes de configure_logging() rodar).
        "root": {
            "level": level,
            "handlers": ["default"],
        },
    }


def configure_logging() -> None:
    """Configura structlog + stdlib logging. Idempotente o suficiente para ser
    chamada no startup da API e do worker."""
    level = logging.getLevelName(settings.logging.log_level)
    pre_chain = _build_pre_chain()

    # structlog nativo: aplica a pre_chain e entrega ao ProcessorFormatter da stdlib.
    structlog.configure(
        processors=[*pre_chain, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )

    # Formatter único; reusado pelo handler raiz.
    formatter = _build_formatter()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Fail-fast: valida o formatter antes de instalá-lo no root.
    _self_test(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # uvicorn.access: silenciado. Nosso LoggingMiddleware já loga cada request
    # com mais contexto. (Mesma decisão do dictConfig acima; replicada aqui
    # porque configure_logging() pode rodar em contextos sem --log-config,
    # como dentro do worker Celery.)
    access = logging.getLogger("uvicorn.access")
    access.handlers.clear()
    access.propagate = False

    # Garante que estes loggers propaguem para o nosso handler raiz, descartando
    # quaisquer handlers próprios que o dictConfig do uvicorn possa ter
    # instalado neles. Resultado: uma única linha por log, no formato certo.
    for name in (
        "uvicorn",
        "uvicorn.error",
        "sqlalchemy.engine",
        "celery",
        "watchfiles",
        "watchfiles.main",
        "watchfiles.watcher",
    ):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True
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
