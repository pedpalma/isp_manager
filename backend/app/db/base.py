# Base declarativa do SQLAlchemy.

# Mapa de chaves do SQLAlchemy -> nosso prefixo:
# ix -> idx_ (índices)
# uq -> uq_ (unique)
# ck -> chk_ (check)
# fk -> fk_ (foreign key)
# pk -> pk_ (primary key)

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION: dict[str, str] = {
    "ix": "idx_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "chk_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base de todos os models ORM. Models de domínio herdam desta classe"""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
