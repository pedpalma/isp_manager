# Model ORM da tabela `manufacturer`.
#
# A tabela JÁ existe no banco (criada pela migration 0001_initial_schema do
# Marco 4 com o DDL.sql). Este model apenas MAPEIA as colunas para que o
# SQLAlchemy possa fazer SELECT/INSERT/UPDATE.
#
# Nenhuma migration nova é necessária para o Marco 9.

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin


class Manufacturer(Base, TimestampMixin):
    """Fabricante de equipamentos (Huawei, ZTE, Fiberhome, Nokia, etc.)."""

    __tablename__ = "manufacturer"

    # `server_default=text("gen_random_uuid()")` é OBRIGATÓRIO aqui. Sem ele,
    # o SQLAlchemy desconhece que o banco gera o UUID e tenta enviar NULL no
    # INSERT, violando o NOT NULL implícito da PK. Com ele, o ORM:
    #   1) sabe que o servidor gera o valor,
    #   2) OMITE a coluna do INSERT (deixando o DDL `DEFAULT gen_random_uuid()` agir),
    #   3) lê o valor gerado via RETURNING automático.
    manufacturer_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # `unique=True` aqui só serve para o ORM "saber" da unicidade. A
    # restrição real já está no banco (uq_manufacturer_slug do DDL).
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    # created_at e updated_at vêm do TimestampMixin.

    def __repr__(self) -> str:
        return f"<Manufacturer slug={self.slug!r} active={self.active}>"
