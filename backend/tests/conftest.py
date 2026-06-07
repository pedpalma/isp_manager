# Config geral dos testes
import os

os.environ.setdefault("ISP_APP_DB_PASSWORD", "test-app-pass")
os.environ.setdefault("ISP_MIGRATOR_DB_PASSWORD", "test-migrator-pass")
os.environ.setdefault("API_SECRET_KEY", "x" * 48)
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("LOG_FORMAT", "json")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.errors import register_error_handlers
from app.api.middleware.logging import LoggingMiddleware
from app.api.middleware.request_id import RequestIDMiddleware
from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging import configure_logging, get_request_id


@pytest.fixture(scope="session", autouse=True)
def _logging() -> None:
    # Garante o pipeline de log configurado
    configure_logging()


def _build_app() -> FastAPI:
    app = FastAPI()
    # Mesma ordem do main. logging primeiro, request_id depois
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)
    register_error_handlers(app)

    @app.get("/ok")
    def ok() -> dict[str:bool]:
        return {"ok": True}

    @app.get("/whoami")
    def whoami() -> dict[str : str | None]:
        # Prova que o request_id amarrado pelo middleware está disponível para o handler
        return {"request_id": get_request_id()}

    @app.get("/notfound")
    def notfound() -> None:
        return NotFoundError("ONU não encontrada", details={"serial": "ABC123"})

    @app.get("/conflict")
    def conflict() -> None:
        return ConflictError("Serial já provisionado")

    @app.get("/needint")
    def needint(n: int) -> dict[str:int]:
        return {"n": n}

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("explosão inesperada")

    return app


@pytest.fixture
def client() -> TestClient:
    return TestClient(_build_app(), raise_server_exceptions=False)
