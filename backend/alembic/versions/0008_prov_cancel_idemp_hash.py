"""
provisioning: canceled status + idempotency payload hash

Marco de Saneamento — Rodada 3.

Duas mudanças aditivas:
1. `ProvisioningStatus.CANCELED` no enum Postgres (rota POST /cancel).
2. `provisioning_order.idempotency_payload_hash TEXT` (idempotência HTTP
   verdadeira: mesmo key + mesmo payload devolve a ordem existente com
   200 OK; key igual + payload diferente devolve 409).

Revision ID: 0008_prov_cancel_idemp_hash
Revises: 0007_prov_order_active_unique
Create Date: 2026-07-08

Nota sobre o revision ID: alembic_version.version_num é VARCHAR(32).
Nome anterior (`0008_prov_cancel_and_idempotency_hash`, 37 chars)
estourou o limite; encurtado para 27 chars. Padrão do projeto costuma
ficar bem próximo do limite (0007 = 29 chars); mantenha revision IDs
curtos daqui em diante.
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008_prov_cancel_idemp_hash"
down_revision: str | None = "0007_prov_order_active_unique"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE provisioning_status_enum ADD VALUE IF NOT EXISTS 'canceled'"
    )

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
