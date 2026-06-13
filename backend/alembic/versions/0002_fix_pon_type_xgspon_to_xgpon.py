"""
fix pon_type_enum: rename XGSPON to XG-PON
Revision ID: 0002_fix_pon_type
Revises: 0001_initial_schema
Create Date: 2026-06-13
"""
from __future__ import annotations

from alembic import op

revision = "0002_fix_pon_type"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None

def upgrade() -> None:
    """Renomeia rótulo do enum. Operação atômica e barata.
    Diferente do 0001 (que usa cursor DBAPI cru pelo volume de DDL e por algumas
    operações que não toleram bloco de transação), aqui um `op.execute` simples
    basta: ALTER TYPE ... RENAME VALUE roda dentro de transação no PG 10+."""
    op.execute("ALTER TYPE pon_type_enum RENAME VALUE 'XGSPON' TO 'XG-PON'")

def downgrade() -> None:
    op.execute("ALTER TYPE pon_type_enum RENAME VALUE 'XG-PON' TO 'XGSPON'")
