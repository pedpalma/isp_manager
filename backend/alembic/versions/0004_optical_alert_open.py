"""optical alert open uniqueness

Revision ID: 0004_optical_alert_open
Revises: 0003_collection_running_unique
Create Date: 2026-06-24 13:00:00.000000
"""
from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_optical_alert_open"
down_revision: str | None = "0003_collection_running_unique"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    """Cria índice único parcial em optical_alert_event.

    Garante que so existe UM alerta 'open' por (onu_id, metric_name).
    CREATE INDEX e transacional em PostgreSQL 10+, op.execute basta.
    """
    op.execute(
        """
        CREATE UNIQUE INDEX uq_optical_alert_open
            ON optical_alert_event (onu_id, metric_name)
            WHERE status = 'open'
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_optical_alert_open")
