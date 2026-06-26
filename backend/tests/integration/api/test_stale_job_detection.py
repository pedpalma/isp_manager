# Teste de integração da task detect_stale_jobs.
# via task agendada.
# Setup: insere job 'running' com started_at antigo via sync engine, roda
# a task em foreground (eager) e verifica que o status virou 'failed'.

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import create_engine, text

from app.core.config import settings
from app.tasks.collection import detect_stale_jobs
from tests.integration.api._olt_mock import setup_inventory
from tests.integration.api.test_auth import _bootstrap_admin


def _sync_engine():
    return create_engine(settings.database.build_app_sync_url())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)  # noqa: UP017


def _insert_running_job_with_age(olt_id, age_minutes: int) -> str:
    """Insere um collection_job em 'running' com started_at simulado."""
    engine = _sync_engine()
    job_id = str(uuid4())
    started_at = _utcnow() - timedelta(minutes=age_minutes)
    try:
        with engine.connect() as conn, conn.begin():
            conn.execute(
                text(
                    """
                    INSERT INTO collection_job (
                        collection_job_id, olt_id, job_type, trigger_type,
                        status, started_at, created_at, retry_count
                    ) VALUES (
                        :id, :olt, 'discovery', 'manual',
                        CAST('running' AS job_status_enum), :started, :started, 0
                    )
                    """
                ),
                {
                    "id": job_id,
                    "olt": str(olt_id),
                    "started": started_at,
                },
            )
    finally:
        engine.dispose()
    return job_id


def _get_job_status(job_id: str) -> tuple[str, str | None]:
    engine = _sync_engine()
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT status, error_message FROM collection_job WHERE collection_job_id = :id"
                ),
                {"id": job_id},
            ).first()
        assert row is not None
        return row[0], row[1]
    finally:
        engine.dispose()


def test_stale_running_job_is_marked_failed(real_client):
    headers, _ = _bootstrap_admin(real_client)
    inv = setup_inventory(real_client, headers)
    # threshold default e configurável; usa um valor que esta com certeza
    # além do default.
    job_id = _insert_running_job_with_age(inv["olt_id"], age_minutes=60)

    result = detect_stale_jobs.apply().get()
    assert job_id in result["stale_jobs"]

    status, err = _get_job_status(job_id)
    assert status == "failed"
    assert err is not None
    assert "stale" in err.lower()


def test_recent_running_job_is_not_touched(real_client):
    headers, _ = _bootstrap_admin(real_client)
    inv = setup_inventory(real_client, headers)
    job_id = _insert_running_job_with_age(inv["olt_id"], age_minutes=1)

    result = detect_stale_jobs.apply().get()
    assert job_id not in result["stale_jobs"]

    status, _ = _get_job_status(job_id)
    assert status == "running"
