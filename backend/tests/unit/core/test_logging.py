import json
import logging

import structlog

from app.core.logging import (
    bind_request_id,
    clear_request_context,
    configure_logging,
    get_logger,
    get_request_id,
    get_uvicorn_log_config,
    make_uvicorn_formatter,
)


def test_configure_logging_runs_and_passes_self_test():
    # Não deve levantar; o _self_test interno valida o formatter.
    configure_logging()
    assert get_logger("x") is not None


def test_formatter_emits_valid_json():
    configure_logging()
    root = logging.getLogger()
    assert root.handlers, "root deveria ter um handler após configure_logging"
    formatter = root.handlers[0].formatter
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="evento.teste",
        args=(),
        exc_info=None,
    )
    rendered = formatter.format(record)
    data = json.loads(rendered)  # se não for JSON válido, levanta
    assert data["event"] == "evento.teste"
    assert data["level"] == "info"
    assert "timestamp" in data


def test_request_id_helpers_roundtrip():
    clear_request_context()
    assert get_request_id() is None
    bind_request_id("req-123")
    assert get_request_id() == "req-123"
    clear_request_context()
    assert get_request_id() is None


def test_uvicorn_log_config_shape():
    """O dictConfig precisa ter as chaves obrigatórias do logging.config e
    referenciar a factory correta. Se alguma quebrar, o uvicorn falha ao
    aplicar --log-config no boot e a API não sobe."""
    cfg = get_uvicorn_log_config()

    # Versão obrigatória pelo logging.config.dictConfig.
    assert cfg["version"] == 1

    # CRÍTICO: precisa permanecer False para não silenciar loggers já criados
    # pelo uvicorn antes do dictConfig rodar.
    assert cfg["disable_existing_loggers"] is False

    # Factory pointer tem que apontar para o caminho importável real.
    assert cfg["formatters"]["structlog"]["()"] == "app.core.logging.make_uvicorn_formatter"

    # Handler default existe e aponta para o formatter "structlog".
    assert cfg["handlers"]["default"]["formatter"] == "structlog"
    assert cfg["handlers"]["default"]["class"] == "logging.StreamHandler"

    # Loggers do uvicorn configurados.
    assert "uvicorn" in cfg["loggers"]
    assert "uvicorn.error" in cfg["loggers"]
    assert "uvicorn.access" in cfg["loggers"]

    # Root tem handler default.
    assert "default" in cfg["root"]["handlers"]


def test_make_uvicorn_formatter_returns_processor_formatter():
    """A factory referenciada pelo dictConfig precisa devolver uma instância
    de ProcessorFormatter. Se devolver outro tipo, o dictConfig do uvicorn
    quebra com erro pouco óbvio no boot."""
    fmt = make_uvicorn_formatter()
    assert isinstance(fmt, structlog.stdlib.ProcessorFormatter)
    assert isinstance(fmt, logging.Formatter)


def test_uvicorn_formatter_produces_valid_json_end_to_end():
    """Empurra um LogRecord pelo formatter retornado pela factory do uvicorn
    e valida que o resultado é JSON parseável com os campos esperados.
    Esta é a garantia de que os dois caminhos (configure_logging() e
    --log-config) produzem saída do mesmo formato."""
    fmt = make_uvicorn_formatter()
    record = logging.LogRecord(
        name="uvicorn.error",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Started server process [1]",
        args=(),
        exc_info=None,
    )
    rendered = fmt.format(record)
    data = json.loads(rendered)
    assert data["event"] == "Started server process [1]"
    assert data["level"] == "info"
    assert data["logger"] == "uvicorn.error"
    assert "timestamp" in data
