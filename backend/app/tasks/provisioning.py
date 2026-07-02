# Task Celery do domínio provisioning

from __future__ import annotations

from uuid import UUID

import structlog

from app.celery_app import celery_app

log = structlog.get_logger(__name__)


@celery_app.task(name="app.tasks.provisioning.run_provisioning_order", autoretry_for=())
def run_provisioning_order(provisioning_order_id: str) -> str:
    """Dispara o ciclo de provisionamento para uma ordem pedente."""

    from app.domains.provisioning.services.provisioning_worker import (
        run_provisioning_order_sync,
    )

    order_id = UUID(provisioning_order_id)
    log.info("provisioning.task.received", provisioning_order_id=str(order_id))
    run_provisioning_order_sync(order_id)
    log.info("provisioning.task.completed", provisioning_order_id=str(order_id))
    return str(order_id)
