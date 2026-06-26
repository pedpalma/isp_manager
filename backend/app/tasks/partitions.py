# Tasks Celery de manutenção de partições mensais de optical_reading.

# Três tasks:
# - ensure_optical_partitions: cria partições futuras (look-ahead 3 meses).
#   Idempotente via CREATE TABLE IF NOT EXISTS na função SQL ja existente.
#   Agendada DIARIAMENTE no beat_schedule.
# - drop_old_optical_partitions: drop de partições mais antigas que a
#   retenção (default 90 dias). Agendada SEMANALMENTE.
# - Beat schedule definido em app/celery_app.py.

# D17.3 fechada: zero cron externo. Toda gestão de partições vive aqui.

# Privilégios: o role isp_app NÃO tem CREATE/DROP em public por design.
# A migration 0005 elevou create_optical_reading_partition e
# drop_optical_reading_partition a SECURITY DEFINER, com owner
# isp_migrator. As tasks chamam essas funções, NÃO emitem DDL direto.

from __future__ import annotations

from datetime import date, timedelta

import structlog
from sqlalchemy import text

from app.celery_app import celery_app
from app.core.config import settings
from app.db.session_sync import session_scope

log = structlog.get_logger(__name__)

# Look-ahead default: cria mês atual + 3 meses a frente.
_LOOK_AHEAD_MONTHS = 3


def _first_of_month(d: date) -> date:
    return d.replace(day=1)


def _add_months(d: date, months: int) -> date:
    """Soma `months` ao primeiro dia do mês de `d`. Implementação manual
    para não depender de dateutil."""
    year = d.year + (d.month - 1 + months) // 12
    month = (d.month - 1 + months) % 12 + 1
    return date(year, month, 1)


@celery_app.task(name="app.tasks.partitions.ensure_optical_partitions", autoretry_for=())
def ensure_optical_partitions() -> dict[str, int]:
    """Garante partições do mês corrente + N meses a frente.

    Chama create_optical_reading_partition (SECURITY DEFINER, owner
    isp_migrator) que internamente faz CREATE TABLE IF NOT EXISTS.
    Idempotente."""
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
    """Drop de partições com mês anterior a cutoff (default 90 dias).

    Lista as filhas de optical_reading via pg_inherits + pg_class e
    interpreta o sufixo YYYY_MM. Partição 'default' (safety net) é
    preservada por design.

    O DROP TABLE em si é delegado a drop_optical_reading_partition
    (SECURITY DEFINER, owner isp_migrator) porque isp_app não tem
    privilégio DDL no schema."""
    retention_days = settings.optical.partition_retention_days
    cutoff = date.today() - timedelta(days=retention_days)
    cutoff_first = _first_of_month(cutoff)

    dropped: list[str] = []
    with session_scope() as db:
        # Lista partições filhas de optical_reading.
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
        candidates: list[str] = []
        for (name,) in rows:
            # default partition tem nome optical_reading_default; preserva.
            if name == "optical_reading_default":
                continue
            # Espera prefixo optical_reading_YYYY_MM.
            suffix = name.removeprefix("optical_reading_")
            try:
                year_str, month_str = suffix.split("_", 1)
                year = int(year_str)
                month = int(month_str)
            except (ValueError, AttributeError):
                log.warning(
                    "optical.partitions.unrecognized_name",
                    partition_name=name,
                )
                continue
            part_date = date(year, month, 1)
            if part_date < cutoff_first:
                candidates.append(name)

        for name in candidates:
            # Função valida o nome novamente e roda DROP TABLE IF EXISTS
            # com privilegio do owner (isp_migrator).
            db.execute(
                text("SELECT drop_optical_reading_partition(:n)"),
                {"n": name},
            )
            dropped.append(name)

    log.info(
        "optical.partitions.dropped",
        retention_days=retention_days,
        dropped_count=len(dropped),
        partitions=dropped,
    )
    return {"dropped": dropped}
