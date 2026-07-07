# Model ORM de olt_command_profile

from __future__ import annotations

from datetime import datetime  # noqa: F401
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin
from app.domains.inventory.enums import AccessProtocol


class OltCommandProfile(Base, TimestampMixin):
    """Perfil de comportamento de comando por olt_model + firmware + protocolo."""

    __tablename__ = "olt_command_profile"

    olt_command_profile_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    olt_model_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("olt_model.olt_model_id"),
        nullable=False,
    )
    firmware_version: Mapped[str] = mapped_column(Text, nullable=False)
    access_protocol: Mapped[AccessProtocol] = mapped_column(
        PG_ENUM(
            AccessProtocol,
            name="access_protocol_enum",
            create_type=False,
            values_callable=lambda e: [v.value for v in e],
        ),
        server_default=text("'SSH'"),
        nullable=False,
    )
    version_constraint: Mapped[str | None] = mapped_column(Text, nullable=True)
    parser_profile: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )

    def __repr__(self) -> str:
        return (
            f"<OltCommandProfile id={self.olt_command_profile_id} "
            f"olt_model_id={self.olt_model_id} firmware={self.firmware_version!r} "
            f"protocol={self.access_protocol} active={self.active}>"
        )
