from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.routes import health
from app.core.config import get_settings
from app.db.session import dispose_engine, init_engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Ciclo de vida do app
    # Startup
    init_engine()
    yield
    # Shutdown
    await dispose_engine()


def create_app() -> FastAPI:
    # Factory de apps, facilita testes
    settings = get_settings()

    app = FastAPI(
        title=settings.app.app_name,
        version=settings.app.app_version,
        lifespan=lifespan,
        # mudar para false quando for para prod
        debug=settings.app.expose_internal_errors(),
        docs_url="/docs" if settings.app.enable_api_docs else None,
        redoc_url="/redoc" if settings.app.enable_api_docs else None,
        openapi_url="/openapi.json" if settings.app.enable_api_docs else None,
    )

    app.include_router(health.router)

    return app
