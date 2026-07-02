# Unique parcial que impede duas ordens ativas para a mesma ONU.

# Index parcial WHERE status IN estados ativos.

# Estados considerados "ativos" para bloqueio de nova ordem:
# pending: ordem criada, aguardando pickup do worker
# validating: worker segurando o lock, resolvendo command_keys
# running: worker executando comandos na OLT

# Estados terminais (não bloqueiam nova ordem):
# success | failed | rolled_back | partial

from __future__ import annotations

from alembic import op

# Revision identifiers, used by Alembic
revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

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
