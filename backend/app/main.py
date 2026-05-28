# Entrypoint da aplicação FastAPI.

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.routes import health
from app.core.config import settings
from app.db.session import dispose_engine, init_engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Ciclo de vida: startup antes do yield, shutdown depois."""
    # STARTUP
    init_engine()
    yield
    # SHUTDOWN
    await dispose_engine()


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

    # Health checks (fora do prefixo /api/v1, contrato de infraestrutura).
    app.include_router(health.router)

    return app


app = create_app()
