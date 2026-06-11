# Tipos SQLAlchemy reutilizáveis do projeto.

# InetStr: garante que uma coluna INET do Postgres seja SEMPRE
# vista como `str` no lado Python, tanto na escrita quanto na leitura,
# independentemente de o driver (asyncpg) decidir devolver um objeto
# `ipaddress.IPv4Address` / `IPv6Address`.

from __future__ import annotations

from typing import Any

from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.types import TypeDecorator


class InetStr(TypeDecorator):
    """Coluna INET nativa do Postgres, exposta como `str` no Python.

    - process_bind_param: o que vai para o banco. Aceita str ou objeto ipaddress e normaliza para str. O Postgres valida o formato do INET.
    - process_result_value: o que volta do banco. Força str, neutralizando o codec do asyncpg (que poderia devolver um objeto ipaddress)."""

    impl = INET
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        return str(value)
