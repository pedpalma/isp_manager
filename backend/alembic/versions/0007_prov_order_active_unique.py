from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_prov_order_active_unique"
down_revision: str | None = "0006_partition_function_recreate"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE UNIQUE INDEX uq_provisioning_order_active
        ON provisioning_order (onu_id)
        WHERE onu_id IS NOT NULL
        AND status IN ('pending', 'validating', 'running')
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_provisioning_order_active")
