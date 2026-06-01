"""
initial schema

Cria todo o schema inicial a partir do arquivo SQL raw `alembic/sql/0001_initial.sql`

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-03-31
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Union

from alembic import op

# Revision identifiers, usados pelo Alembic
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Caminho do .sql
_ALEMBIC_DIR = Path(__file__).resolve().parent.parent
_SQL_FILE = _ALEMBIC_DIR / "sql" / "0001_initial.sql"


def _exec_raw(sql: str) -> None:
    # Executa SQL cru pelo cursor DBAPI

    # Conexão crua
    raw_conn = op.get_bind().connection
    cur = raw_conn.cursor()
    try:
        cur.execute(sql)
    finally:
        cur.close()


def upgrade() -> None:
    _exec_raw(_SQL_FILE.read_text(encoding="utf-8"))
    # Reforça a imutabilidade de audit_log no nível de role.
    _exec_raw(
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
    # Reverte o schema removendo objetos criados pelo 0001
    _exec_raw(
        """
        DO $$
        DECLARE
            r RECORD;
        BEGIN
            -- 1) Tabelas (CASCADE resolve FKs, índices, triggers e partições).
            FOR r IN
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public'
                  AND tablename <> 'alembic_version'   -- preserva a tabela de controle do Alembic
            LOOP
                EXECUTE format('DROP TABLE IF EXISTS public.%I CASCADE', r.tablename);
            END LOOP;
 
            -- 2) Tipos ENUM (CREATE TYPE não é idempotente; precisa sair para
            --    o re-upgrade não falhar com "type already exists").
            FOR r IN
                SELECT t.typname
                FROM pg_type t
                JOIN pg_namespace n ON n.oid = t.typnamespace
                WHERE n.nspname = 'public' AND t.typtype = 'e'
            LOOP
                EXECUTE format('DROP TYPE IF EXISTS public.%I CASCADE', r.typname);
            END LOOP;
        END
        $$;
 
        -- 3) Funções desta migration, nomeadas para NÃO tocar em funções de
        --    extensões (ex.: gen_random_uuid do pgcrypto).
        DROP FUNCTION IF EXISTS public.create_optical_reading_partition(date) CASCADE;
        DROP FUNCTION IF EXISTS public.ensure_onu_runtime_state() CASCADE;
        DROP FUNCTION IF EXISTS public.set_updated_at() CASCADE;
        DROP FUNCTION IF EXISTS public.audit_log_immutable() CASCADE;
        """
    )
