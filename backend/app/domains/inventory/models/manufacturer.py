# Model ORM da tabela `manufacturer`.
# Este model MAPEIA as colunas para que o SQLAlchemy possa fazer SELECT/INSERT/UPDATE.

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin


class Manufacturer(Base, TimestampMixin):
    """Fabricante de equipamentos (Huawei, ZTE, Fiberhome, Nokia, etc.)."""

    __tablename__ = "manufacturer"

    # `manufacturer_id` sem default no ORM. O DDL tem
    # `DEFAULT gen_random_uuid()`; deixamos o Postgres gerar e o SQLAlchemy
    # recupera o valor via RETURNING automático após o INSERT.
    manufacturer_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)

    # `unique=True` aqui só serve para o ORM "saber" da unicidade. A
    # restrição real já está no banco (uq_manufacturer_slug do DDL).
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # created_at e updated_at vem do mixin de timestamp

    def __repr__(self) -> str:
        # Útil em logs/debug.
        return f"<Manufacturer slug={self.slug!r} active={self.active}>"
