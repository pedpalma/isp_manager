# Entrypoint da aplicação FastAPI.

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_error_handlers
from app.api.middleware.logging import LoggingMiddleware
from app.api.middleware.request_id import RequestIDMiddleware
from app.api.v1.routes import diagnostics, health
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.session import dispose_engine, init_engine

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Ciclo de vida: startup antes do yield, shutdown depois."""
    # STARTUP
    init_engine()
    log.info("app.startup", app_version=settings.app.app_version, env=settings.app.app_env)
    yield
    # SHUTDOWN
    await dispose_engine()
    log.info("app.shutdown")


def create_app() -> FastAPI:
    """Factory de aplicação."""
    # Configura o logging ANTES de qualquer coisa, para que até os logs de
    # inicialização (incluindo os do uvicorn) saiam no formato estruturado.
    configure_logging()

    app = FastAPI(
        title=settings.app.app_name,
        version=settings.app.app_version,
        lifespan=lifespan,
        debug=settings.app.expose_internal_errors,
        # Em produção, desabilitar docs se ENABLE_API_DOCS=false.
        docs_url="/docs" if settings.app.enable_api_docs else None,
        redoc_url="/redoc" if settings.app.enable_api_docs else None,
        openapi_url="/openapi.json" if settings.app.enable_api_docs else None,
    )

    # Middlewares
    # Fluxo de entrada de uma requisição: CORS -> RequestID -> Logging -> rota.

    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.app.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        # X-Request-ID permitido na requisição (correlação iniciada no cliente).
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        # X-Request-ID exposto para o navegador conseguir LER o id na resposta.
        expose_headers=["X-Request-ID"],
        # Cacheia o resultado do preflight por 10 min.
        max_age=600,
    )

    # Handlers globais de erro (resposta JSON padronizada)
    register_error_handlers(app)

    # Rotas
    # Health fora do prefixo /api/v1 (contrato de infraestrutura).
    app.include_router(health.router)
    # Diagnóstico sob o prefixo de versão.
    app.include_router(diagnostics.router, prefix="/api/v1")

    return app


app = create_app()
