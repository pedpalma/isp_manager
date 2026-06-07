# Configuração compartilhada dos testes.

import os

os.environ.setdefault("ISP_APP_DB_PASSWORD", "test-app-pass")
os.environ.setdefault("ISP_MIGRATOR_DB_PASSWORD", "test-migrator-pass")
os.environ.setdefault("API_SECRET_KEY", "x" * 48)
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("LOG_FORMAT", "json")

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.api.errors import register_error_handlers  # noqa: E402
from app.api.middleware.logging import LoggingMiddleware  # noqa: E402
from app.api.middleware.request_id import RequestIDMiddleware  # noqa: E402
from app.core.exceptions import ConflictError, NotFoundError  # noqa: E402
from app.core.logging import configure_logging, get_request_id  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _logging() -> None:
    # Garante o pipeline de logging configurado (e passa pelo self-test).
    configure_logging()


def _build_app() -> FastAPI:
    app = FastAPI()
    # Mesma ordem do main.py real: logging primeiro, request_id depois
    # (request_id vira o mais externo).
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)
    register_error_handlers(app)

    @app.get("/ok")
    def ok():
        return {"ok": True}

    @app.get("/whoami")
    def whoami():
        # Prova que o request_id amarrado pelo middleware está disponível ao handler.
        return {"request_id": get_request_id()}

    @app.get("/notfound")
    def notfound():
        raise NotFoundError("ONU não encontrada.", details={"serial": "ABC123"})

    @app.get("/conflict")
    def conflict():
        raise ConflictError("Serial já provisionado.")

    @app.get("/needint")
    def needint(n: int):
        return {"n": n}

    @app.get("/boom")
    def boom():
        raise RuntimeError("explosão inesperada")

    return app


@pytest.fixture()
def client() -> TestClient:
    # raise_server_exceptions=False
    return TestClient(_build_app(), raise_server_exceptions=False)
