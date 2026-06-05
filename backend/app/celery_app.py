# Configuração da aplicação Celery (broker + backend de resultados + opções)
from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "isp_manager",
    broker=settings.redis.build_broker_url(),
    backend=settings.redis.build_result_backend_url(),
    include=[
        "app.tasks.health",
        # módulos de tasks adicionais entram aqui
    ],
)

celery_app.conf.update(
    # Define explicitamente o retry de conexão ao broker no startup.
    broker_connection_retry_on_startup=True,
    # Serialização: apenas JSON.
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # UTC em todo lugar.
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Um worker pega uma tarefa por vez.
    worker_prefetch_multiplier=1,
    # Resultados expiram em 1h.
    result_expires=3600,
    # Marca a task como 'started' assim que o worker pega.
    task_track_started=True,
)

# Registra os sinais (correlação de request_id API↔worker + logging do worker).
# Import no fim, depois de celery_app existir, para evitar import circular.
# Como API e worker importam este módulo, ambos passam a ter os sinais ligados.
import app.core.celery_signals  # noqa: E402, F401
