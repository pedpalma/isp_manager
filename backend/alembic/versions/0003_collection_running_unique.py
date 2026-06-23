"""collection_job: partial UNIQUE index on (olt_id, job_type)
WHERE status IN ('pending','running')

Garante idempotência concorrente do POST /collection-jobs.
O índice idx_collection_job_running já existe no 0001 mas é NÃO-único
(serve para hot lookup de jobs ativos).
Aqui foi adicionado um SEGUNDO índice, parcial e ÚNICO,
sobre as MESMAS colunas + predicado, especificamente para forçar
um job ativo por (olt, job_type) ao nível do banco.

Disparo de conflito: INSERT que viole este índice é capturado pelo
CollectionJobService como IntegrityError e traduzido em ConflictError 409.

Revision ID: 0003_collection_running_unique
Revises: 0002_fix_pon_type
Create Date: 2026-06-22
"""

from __future__ import annotations

from alembic import op

revision = "0003_collection_running_unique"
down_revision = "0002_fix_pon_type"
branch_labels = None
depends_on = None

def upgrade() -> None:
    """Cria o índice único parcial."""
    op.execute(
        """
        CREATE UNIQUE INDEX uq_collection_job_running
            ON collection_job (olt_id, job_type)
            WHERE status IN ('pending', 'running')
        """
    )

def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_collection_job_running")
