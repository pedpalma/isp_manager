# Testa a LÓGICA de correlação API <-> worker sem precisar de broker real:
# chama os handlers de sinal diretamente com objetos simulados.

from types import SimpleNamespace

from app.core.celery_signals import (
    _bind_request_id,
    _clear_request_id,
    _inject_request_id,
)
from app.core.logging import bind_request_id, clear_request_context, get_request_id


def test_inject_request_id_into_headers():
    clear_request_context()
    bind_request_id("rid-publish")
    headers: dict[str, object] = {}
    _inject_request_id(headers=headers)
    assert headers["request_id"] == "rid-publish"
    clear_request_context()


def test_inject_noop_when_no_request_id():
    clear_request_context()
    headers: dict[str, object] = {}
    _inject_request_id(headers=headers)
    assert "request_id" not in headers


def test_inject_safe_when_headers_none():
    clear_request_context()
    bind_request_id("rid")
    # não deve levantar quando headers é None
    _inject_request_id(headers=None)
    clear_request_context()


def test_worker_binds_and_clears_request_id():
    clear_request_context()
    fake_task = SimpleNamespace(
        name="app.tasks.health.ping",
        request=SimpleNamespace(request_id="rid-worker", id="task-1"),
    )
    _bind_request_id(task=fake_task)
    assert get_request_id() == "rid-worker"

    _clear_request_id(task=fake_task)
    assert get_request_id() is None


def test_worker_handles_missing_request_id():
    clear_request_context()
    fake_task = SimpleNamespace(name="t", request=SimpleNamespace(id="task-2"))
    _bind_request_id(task=fake_task)  # sem request_id no header
    assert get_request_id() is None
    _clear_request_id(task=fake_task)
