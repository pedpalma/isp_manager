import json
import logging

from app.core.logging import (
    bind_request_id,
    clear_request_context,
    configure_logging,
    get_logger,
    get_request_id,
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
