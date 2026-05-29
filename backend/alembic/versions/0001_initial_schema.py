# Cria todo o schema inicial a partir do arquivo SQL raw
from __future__ import annotations

from pathlib import Path
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ALEMBIC_DIR = Path(__file__).resolve().parent.parent
_SQL_FILE = _ALEMBIC_DIR / "sql" / "0001_initial.sql"


def upgrade() -> None:
    sql = _SQL_FILE.read_text("utf-8")

    bind = op.get_bind()
    bind.exec_driver_sql(sql)
    bind.exec_driver_sql(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'isp_app') THEN
                EXECUTE 'REVOKE UPDATE, DELETE ON audit_log FROM isp_app';
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    # Reverte o schema inicial ao estado vazio (pré-migration).
    bind = op.get_bind()
    bind.exec_driver_sql(
        """
        DROP SCHEMA IF EXISTS public CASCADE;
        CREATE SCHEMA public;
 
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'isp_app') THEN
                EXECUTE 'GRANT USAGE ON SCHEMA public TO isp_app';
            END IF;
        END
        $$;
        """
    )
