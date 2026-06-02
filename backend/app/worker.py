# Entrypoin do Celery
from __future__ import annotations

from celery.signals import worker_process_shutdown

from app.celery_app import celery_app  # noqa: F401
from app.db.session_sync import dispose_sync_engine


@worker_process_shutdown.connect
def _dispose_engine_on_shutdown(**_kwargs: object) -> None:
    # Fecha o pool de conexões sincronas quando encerra o worker
    dispose_sync_engine()
