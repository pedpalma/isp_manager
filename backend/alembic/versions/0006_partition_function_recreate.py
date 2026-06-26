"""partition function recreate with security definer header

Revision ID: 0006_partition_function_recreate
Revises: 0005_partition_security_definer
Create Date: 2026-06-26 19:00:00.000000
"""
from __future__ import annotations

from alembic import op

revision: str = "0006_partition_function_recreate"
down_revision: str | None = "0005_partition_security_definer"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    """Recria create_optical_reading_partition declarando SECURITY DEFINER
    e SET search_path no header. Adiciona SET search_path em
    drop_optical_reading_partition. Garante GRANT CREATE para isp_migrator
    no schema public como defesa em profundidade (no-op se ja tem)."""
    op.execute("GRANT CREATE ON SCHEMA public TO isp_migrator")

    op.execute(
        """
        CREATE OR REPLACE FUNCTION create_optical_reading_partition(target_month DATE)
        RETURNS TEXT
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
        DECLARE
            part_name   TEXT;
            range_start TEXT;
            range_end   TEXT;
            month_start DATE;
        BEGIN
            month_start := date_trunc('month', target_month)::date;
            part_name   := 'optical_reading_' || to_char(month_start, 'YYYY_MM');
            range_start := to_char(month_start, 'YYYY-MM-DD');
            range_end   := to_char(month_start + INTERVAL '1 month', 'YYYY-MM-DD');

            EXECUTE format(
                'CREATE TABLE IF NOT EXISTS %I PARTITION OF optical_reading
                FOR VALUES FROM (%L) TO (%L)',
                part_name, range_start, range_end
            );

            RETURN part_name;
        END;
        $$;
        """
    )

    op.execute(
        "ALTER FUNCTION create_optical_reading_partition(DATE) OWNER TO isp_migrator"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION create_optical_reading_partition(DATE) TO isp_app"
    )

    op.execute(
        "ALTER FUNCTION drop_optical_reading_partition(TEXT) "
        "SET search_path = public, pg_temp"
    )

    op.execute(
        """
        COMMENT ON FUNCTION create_optical_reading_partition(DATE) IS
            'Cria partição mensal de optical_reading. SECURITY DEFINER + search_path '
            'fixo em public permite que isp_app invoque sem ter privilegio DDL direto. '
            'Chamar mensalmente via app.tasks.partitions.ensure_optical_partitions.'
        """
    )


def downgrade() -> None:
    """Rollback parcial: remove SET search_path de drop_optical_reading_partition
    e restaura create_optical_reading_partition para o estado da 0005
    (sem search_path explicito, mas ainda SECURITY DEFINER)."""
    op.execute(
        "ALTER FUNCTION drop_optical_reading_partition(TEXT) RESET search_path"
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION create_optical_reading_partition(target_month DATE)
        RETURNS TEXT
        LANGUAGE plpgsql
        SECURITY DEFINER
        AS $$
        DECLARE
            part_name   TEXT;
            range_start TEXT;
            range_end   TEXT;
            month_start DATE;
        BEGIN
            month_start := date_trunc('month', target_month)::date;
            part_name   := 'optical_reading_' || to_char(month_start, 'YYYY_MM');
            range_start := to_char(month_start, 'YYYY-MM-DD');
            range_end   := to_char(month_start + INTERVAL '1 month', 'YYYY-MM-DD');
            EXECUTE format(
                'CREATE TABLE IF NOT EXISTS %I PARTITION OF optical_reading
                FOR VALUES FROM (%L) TO (%L)',
                part_name, range_start, range_end
            );
            RETURN part_name;
        END;
        $$;
        """
    )
    op.execute(
        "ALTER FUNCTION create_optical_reading_partition(DATE) OWNER TO isp_migrator"
    )
