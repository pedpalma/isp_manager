# Configuração do Worker Celery (Broker + Backend de resultados + opções)
from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "isp_manager",
)
