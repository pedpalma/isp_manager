# Task Celery de manutenção de partições mensais de optical_reading.

from __future__ import annotations

from datetime import date, timedelta

import structlog
from sqlalchemy import text

from app.celery_app import celery_app
from app.core.config import settings
from app.db.session_sync import session_scope

log = structlog.get_logger(__name__)

# mês atual + 3 meses seguintes
_LOOK_AHEAD_MONTHS = 3


def _first_of_month(d: date) -> date:
    return d.replace(day=1)


def _add_months(d: date, months: int) -> date:
    """Soma 'months' ao primeiro dia do mês de 'd'."""
    year = d.year + (d.month - 1 + months) // 12
    month = (d.month - 1 + months) % 12 + 1
    return date(year, month, 1)


@celery_app.task(name="app.tasks.partitions.ensure_optical_partitions", autoretry_for=())
def ensure_optical_partitions() -> dict[str, int]:
    """Garante partições do mês corrente +N meses a frente."""
    base = _first_of_month(date.today())
    created = 0
    with session_scope() as db:
        for offset in range(_LOOK_AHEAD_MONTHS + 1):
            target = _add_months(base, offset)
            db.execute(
                text("SELECT create_optical_reading_partition(:d)"),
                {"d": target.isoformat()},
            )
            created += 1
    log.info("optical.partitions.ensured", months_processed=created)
    return {"months_processed": created}


@celery_app.task(name="app.tasks.partitions.drop_old_optical_partitions", autoretry_for=())
def drop_old_optical_partitions() -> dict[str, list[str]]:
    """Drop de partições com mês anterior a cutoff (90 dias)."""
    retention_days = settings.optical.partition_retention_days
    cutoff = date.today() - timedelta(days=retention_days)
    cutoff_first = _first_of_month(cutoff)

    dropped: list[str] = []
    with session_scope() as db:
        # Lista partições
        rows = db.execute(
            text(
                """
                SELECT c.relname AS partition_name
                FROM pg_inherits i
                JOIN pg_class c ON c.oid = i.inhrelid
                JOIN pg_class p ON p.oid = i.inhparent
                WHERE p.relname = 'optical_reading'
                """
            )
        ).all()
        for (name,) in rows:
            if name == "optical_reading_default":
                continue
            suffix = name.removeprefix("optical_reading_")
            try:
                year_str, mount_str = suffix.split("_", 1)
                year = int(year_str)
                month = int(mount_str)
            except (ValueError, AttributeError):
                log.warning(
                    "optical.partition.unrecognized_name",
                    partition_name=name,
                )
                continue
            part_date = date(year, month, 1)
            if part_date < cutoff_first:
                # DROP TABLE da partição.
                db.execute(text(f'DROP TABLE IF EXISTS "{name}"'))
                dropped.append(name)
    log.info(
        "optical.partitions.dropped",
        retention_days=retention_days,
        dropped_count=len(dropped),
        partitions=dropped,
    )
    return {"dropped": dropped}
