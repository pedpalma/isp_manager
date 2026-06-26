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
        "app.tasks.collection",
        "app.tasks.partitions",
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
    # Agendamentos periódicos (Celery beat). Idempotentes; reiniciar o
    # beat não executa task fora do horário previsto.
    # - ensure_optical_partitions: cria partições futuras de optical_reading
    #   (look-ahead de 3 meses). Diária. D17.3.
    # - drop_old_optical_partitions: dropa partições além da retenção
    #   (default 90 dias). Semanal. D17.3.
    # - detect_stale_jobs: marca como failed jobs que ficaram 'running' ou
    #   'pending' além do threshold (default 10 min). A cada 5 min. D17.10
    #   e mitigação de P-M16 (janela de órfão entre commit do job e enqueue
    #   da task Celery).
    beat_schedule={
        "ensure-optical-partitions-daily": {
            "task": "app.tasks.partitions.ensure_optical_partitions",
            "schedule": 86400.0,
        },
        "drop-old-optical-partitions-weekly": {
            "task": "app.tasks.partitions.drop_old_optical_partitions",
            "schedule": 604800.0,
        },
        "detect-stale-collection-jobs": {
            "task": "app.tasks.collection.detect_stale_jobs",
            "schedule": 300.0,
        },
    },
)

# Registra os sinais (correlação de request_id API <-> worker + logging do worker).
# Import no fim, depois de celery_app existir, para evitar import circular.
# Como API e worker importam este módulo, ambos passam a ter os sinais ligados.
import app.core.celery_signals  # noqa: E402, F401
