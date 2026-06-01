# Configuração do Worker Celery (Broker + Backend de resultados + opções)
from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "isp_manager",
    broker=settings.redis.build_broker_url(),
    backend=settings.redis.build_result_backend_url(),
    include=[
        "app.tasks.health",
        # Aqui serão incluidas as tasks futuras
    ],
)

celery_app.conf.update(
    # Serialização com JSON
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # UTC
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    # Resultados expiram em 1h
    result_expires=3600,
    # Marca a task como 'started' assim que o worker pega
    task_track_started=True,
)
