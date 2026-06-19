# Model ORM da tabela `user_group`.
# Arquétipo catalog: TimestampMixin, `active`, unicidade TOTAL em `name`
# (uq_user_group_name no DDL: sem WHERE, active=false NÃO libera o nome).

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin


class UserGroup(Base, TimestampMixin):
    """Grupo de usuários. As permissões ficam em `permissions_json`.
    O seed da 0001 ja cria 'Administrador' ({"all": true}), 'Técnico' e 'Visualizador'."""

    __tablename__ = "user_group"

    user_group_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)

    # JSONB com DEFAULT '{}' no DDL. O app sempre envia (schema tem default
    # {}), mas mantém server_default como rede de segurança (mesma postura
    # de robustez extra usada em version de line_profile/service_profile).
    permissions_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # created_at e updated_at vem do TimestampMixin.

    def __repr__(self) -> str:
        return f"<UserGroup name={self.name!r} active={self.active}>"
