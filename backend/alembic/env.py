# Ambiente de execução das migrations do Alembic.

"""
1. Descobre a URL do banco a partir das Settings da aplicação, usando o
role `isp_migrator` (CREATE/ALTER/DROP) e o driver SÍNCRONO psycopg.
O runtime da API usa outro role (`isp_app`) com permissões mínimas.

2. Configura o contexto de migration nos modos online e offline.
"""

from __future__ import annotations

import logging
from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context
from app.core.config import settings

# Objeto de config do Alembic (acesso ao alembic.ini)
config = context.config

# Configura logging a partir das seções do alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

logging = logging.getLogger("alembic.env")

target_metadata = None


def _migrator_url() -> str:
    # URL síncrona (psycopg) do role isp_migrator.
    return str(settings.database.build_migrator_url())


def run_migrations_offline() -> None:
    # Emite SQL sem abrir conexão
    context.configure(
        url=_migrator_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Conecta no banco e aplica as migrations
    connectable = create_engine(_migrator_url(), poolclass=pool.NullPool, future=True)

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, transaction_per_migration=True
        )

        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
