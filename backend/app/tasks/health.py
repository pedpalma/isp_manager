# Tasks de diagnóstico do Worker Celery
from __future__ import annotations

from app.celery_app import celery_app


@celery_app.task(name="app.tasks.health.ping")
def ping() -> str:
    # Serve para confirmar se o worker está up
    return "pong"
