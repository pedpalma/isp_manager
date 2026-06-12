# Model ORM da tabela `olt`.


# Unicidades parciais (WHERE deleted_at IS NULL) vivem no DDL, não aqui:
# - uq_olt_name_active -> (name) com deleted_at IS NULL
# - uq_olt_ip_port_active -> (ip, management_port) com deleted_at IS NULL

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, Text, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import SoftDeleteMixin, TimestampMixin
from app.db.types import InetStr
from app.domains.inventory.enums import AccessProtocol, ConnectionStatus


class Olt(Base, TimestampMixin, SoftDeleteMixin):
    """OLT física cadastrada no inventário.

    Três flags com semânticas distintas:
    - polling_enabled: controla se a Coleta busca dados desta OLT.
    - active: desativação administrativa. NÃO libera o par (ip, porta) nem o name, porque a unicidade parcial olha deleted_at, não active.
    - deleted_at (soft delete): tira a OLT da rede. LIBERA name e (ip, porta) porque sai das unicidades parciais."""

    __tablename__ = "olt"

    olt_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    hostname: Mapped[str | None] = mapped_column(Text, nullable=True)

    # INET nativo via InetStr: sempre str no Python (D11.9).
    ip: Mapped[str] = mapped_column(InetStr, nullable=False)

    # App sempre envia (schema tem default). Só `default` no ORM.
    management_port: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=22,
    )

    access_protocol: Mapped[AccessProtocol] = mapped_column(
        postgresql.ENUM(
            AccessProtocol,
            name="access_protocol_enum",
            create_type=False,
            values_callable=lambda e: [v.value for v in e],
        ),
        nullable=False,
        default=AccessProtocol.SSH,
    )

    firmware_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)

    timezone: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="America/Sao_Paulo",
    )

    polling_enabled: Mapped[bool] = mapped_column(
        postgresql.BOOLEAN,
        nullable=False,
        default=True,
    )

    # FKs. manufacturer_id NÃO mora aqui (vem via olt_model). D11.5:
    # olt_model_id é imutável por PATCH; credential_id é mutável.
    olt_model_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("olt_model.olt_model_id"),
        nullable=False,
    )
    credential_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("credential.credential_id"),
        nullable=False,
    )

    # Campo da Coleta. App NÃO envia no INSERT -> server_default + RETURNING.
    connection_status: Mapped[ConnectionStatus] = mapped_column(
        postgresql.ENUM(
            ConnectionStatus,
            name="connection_status_enum",
            create_type=False,
            values_callable=lambda e: [v.value for v in e],
        ),
        nullable=False,
        server_default=text("'unknown'"),
    )

    # Preenchidos pela Coleta. None até lá.
    last_seen_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    last_collected_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )

    active: Mapped[bool] = mapped_column(
        postgresql.BOOLEAN,
        nullable=False,
        default=True,
    )
    # created_at / updated_at vêm do TimestampMixin.
    # deleted_at vem do SoftDeleteMixin.

    def __repr__(self) -> str:
        return (
            f"<Olt name={self.name!r} ip={self.ip!r} "
            f"port={self.management_port} active={self.active} "
            f"deleted={self.is_deleted}>"
        )
