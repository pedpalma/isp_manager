"""partition security definer for isp_app

Revision ID: 0005_partition_security_definer
Revises: 0004_optical_alert_open
Create Date: 2026-06-26 17:00:00.000000
"""
from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_partition_security_definer"
down_revision: str | None = "0004_optical_alert_open"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    """Eleva privilegio das funções de gestão de partição.

    - ALTER FUNCTION existente para SECURITY DEFINER (criada na 0001).
    - CREATE FUNCTION drop_optical_reading_partition(TEXT) SECURITY DEFINER.
    - GRANT EXECUTE para isp_app.
    """
    op.execute(
        "ALTER FUNCTION create_optical_reading_partition(DATE) OWNER TO isp_migrator"
    )
    op.execute(
        "ALTER FUNCTION create_optical_reading_partition(DATE) SECURITY DEFINER"
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION drop_optical_reading_partition(part_name TEXT)
        RETURNS BOOLEAN AS $$
        DECLARE
            safe_pattern TEXT := '^optical_reading_[0-9]{4}_[0-9]{2}$';
        BEGIN
            IF part_name !~ safe_pattern THEN
                RAISE EXCEPTION 'nome de partição invalido: %', part_name;
            END IF;
            EXECUTE format('DROP TABLE IF EXISTS %I', part_name);
            RETURN TRUE;
        END;
        $$ LANGUAGE plpgsql SECURITY DEFINER;
        """
    )

    op.execute(
        "ALTER FUNCTION drop_optical_reading_partition(TEXT) OWNER TO isp_migrator"
    )

    op.execute(
        "GRANT EXECUTE ON FUNCTION create_optical_reading_partition(DATE) TO isp_app"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION drop_optical_reading_partition(TEXT) TO isp_app"
    )

    op.execute(
        """
        COMMENT ON FUNCTION drop_optical_reading_partition(TEXT) IS
            'Drop seguro de partição mensal de optical_reading. SECURITY DEFINER permite '
            'que isp_app dispare DROP sem ter privilegio DDL direto no schema.'
        """
    )


def downgrade() -> None:
    op.execute(
        "REVOKE EXECUTE ON FUNCTION drop_optical_reading_partition(TEXT) FROM isp_app"
    )
    op.execute(
        "REVOKE EXECUTE ON FUNCTION create_optical_reading_partition(DATE) FROM isp_app"
    )
    op.execute("DROP FUNCTION IF EXISTS drop_optical_reading_partition(TEXT)")
    op.execute(
        "ALTER FUNCTION create_optical_reading_partition(DATE) SECURITY INVOKER"
    )
