# Entrypoint da aplicação FastAPI.

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.errors import register_error_handlers
from app.api.middleware.logging import LoggingMiddleware
from app.api.middleware.request_id import RequestMiddleware
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
    log.info("app.startup", app_version=settings.app.app_version, env_settings=settings.app.app_env)
    yield
    # SHUTDOWN
    await dispose_engine()
    log.info("app.shutdown")


def create_app() -> FastAPI:
    """Factory de aplicação."""
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

    # No Starlette, o middleware adicionado POR ÚLTIMO é o MAIS
    # EXTERNO (roda primeiro no request, por último na resposta).
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RequestMiddleware)

    # Handlers globais de erros
    register_error_handlers(app)

    # Rotas
    # Health checks (fora do prefixo /api/v1, contrato de infraestrutura).
    app.include_router(health.router)
    # Diagnóstico sobre o prefixo da versão
    app.include_router(diagnostics.router, prefix="/api/v1")

    return app


app = create_app()
