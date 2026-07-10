"""
provisioning: canceled status + idempotency payload hash

Revision ID: 0008_prov_cancel_and_idempotency_hash
Revises: 0007_prov_order_active_unique
Create Date: 2026-07-08
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008_prov_cancel_and_idempotency_hash"
down_revision: str | None = "0007_prov_order_active_unique"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # 1. Novo valor no enum. IF NOT EXISTS para idempotência da migration.
    op.execute(
        "ALTER TYPE provisioning_status_enum ADD VALUE IF NOT EXISTS 'canceled'"
    )

    # 2. Coluna nova nullable, para não exigir backfill em ordens antigas.
    op.execute(
        """
        ALTER TABLE provisioning_order
        ADD COLUMN idempotency_payload_hash TEXT
        """
    )


def downgrade() -> None:
    # Coluna: drop é reversível.
    op.execute(
        """
        ALTER TABLE provisioning_order
        DROP COLUMN IF EXISTS idempotency_payload_hash
        """
    )
    pass
