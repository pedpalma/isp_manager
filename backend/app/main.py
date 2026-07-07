# Entrypoint da aplicação FastAPI.


from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_error_handlers
from app.api.middleware.logging import LoggingMiddleware
from app.api.middleware.request_id import RequestIDMiddleware
from app.api.v1.routes import (
    app_users,
    auth,
    chassis,
    collection_jobs,
    credentials,
    diagnostics,
    effective_thresholds,
    health,
    line_profiles,
    manufacturers,
    normalized_commands,
    olt_command_profiles,
    olt_models,
    olts,
    onu_models,
    onus,
    optical_alerts,
    optical_history,
    optical_threshold_policies,
    pending_onus,
    pon_ports,
    provisioning_orders,
    provisioning_templates,
    service_profiles,
    slots,
    topology,
    user_groups,
    vlans,
)
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
    # ORDEM IMPORTA. No Starlette, o ÚLTIMO add_middleware é o mais EXTERNO.
    # Fluxo de entrada de uma requisição: CORS -> RequestID -> Logging -> rota.

    # 1) LoggingMiddleware: loga já com o request_id no contexto.
    # 2) RequestIDMiddleware: amarra/propaga o request_id antes do logging.
    # 3) CORSMiddleware: responde o preflight OPTIONS antes de gerar request_id/log e embrulha TODAS as respostas.
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        # Lista explícita vinda de CORS_ORIGINS. NUNCA "*" com credenciais.
        allow_origins=settings.app.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        # X-Request-ID permitido na requisição (correlação iniciada no cliente).
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        # X-Request-ID exposto para o navegador conseguir LER o id na resposta.
        expose_headers=["X-Request-ID"],
        # Cacheia o resultado do preflight por 10 min (menos OPTIONS repetidos).
        max_age=600,
    )

    # Handlers globais de erro
    register_error_handlers(app)

    # Rotas
    # Health fora do prefixo /api/v1 (contrato de infraestrutura).
    app.include_router(health.router)
    # Sob /api/v1.
    app.include_router(diagnostics.router, prefix="/api/v1")
    app.include_router(manufacturers.router, prefix="/api/v1")
    app.include_router(olt_models.router, prefix="/api/v1")
    app.include_router(onu_models.router, prefix="/api/v1")
    app.include_router(credentials.router, prefix="/api/v1")
    app.include_router(olts.router, prefix="/api/v1")
    app.include_router(chassis.router, prefix="/api/v1")
    app.include_router(slots.router, prefix="/api/v1")
    app.include_router(pon_ports.router, prefix="/api/v1")
    app.include_router(topology.router, prefix="/api/v1")
    app.include_router(vlans.router, prefix="/api/v1")
    app.include_router(line_profiles.router, prefix="/api/v1")
    app.include_router(service_profiles.router, prefix="/api/v1")
    app.include_router(onus.router, prefix="/api/v1")
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(user_groups.router, prefix="/api/v1")
    app.include_router(app_users.router, prefix="/api/v1")
    app.include_router(collection_jobs.router, prefix="/api/v1")
    app.include_router(pending_onus.router, prefix="/api/v1")
    app.include_router(effective_thresholds.router, prefix="/api/v1")
    app.include_router(optical_alerts.router, prefix="/api/v1")
    app.include_router(optical_history.router, prefix="/api/v1")
    app.include_router(optical_threshold_policies.router, prefix="/api/v1")
    app.include_router(provisioning_templates.router, prefix="/api/v1")
    app.include_router(normalized_commands.router, prefix="/api/v1")
    app.include_router(provisioning_orders.router, prefix="/api/v1")
    app.include_router(olt_command_profiles.router, prefix="/api/v1")

    return app


app = create_app()
