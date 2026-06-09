# Enums Python espelhando os ENUMs nativos do Postgres do domínio Inventory.
#
# O DDL.sql já criou os tipos no banco (ex.: connection_status_enum,
# port_status_enum, pon_type_enum). Padrão de uso quando precisarmos:
#
#   from enum import Enum
#   from sqlalchemy.dialects import postgresql
#
#   class ConnectionStatus(str, Enum):
#       UNKNOWN = "unknown"
#       ONLINE = "online"
#       ...
#
#   # No model:
#   connection_status: Mapped[ConnectionStatus] = mapped_column(
#       postgresql.ENUM(
#           ConnectionStatus,
#           name="connection_status_enum",
#           create_type=False,           # <- o tipo JÁ existe no banco
#           values_callable=lambda e: [v.value for v in e],
#       ),
#       nullable=False,
#       default=ConnectionStatus.UNKNOWN,
#   )
#
# Pontos importantes:
#   - `create_type=False`: impede o SQLAlchemy de tentar recriar o tipo
#     (o DDL já criou; recriar daria erro). Decisão D2 do Marco 9.
#   - `values_callable`: garante que o que vai para o banco é a STRING do
#     enum ("online"), e não o nome do membro Python ("ONLINE").
#   - Herdar de `str` (`class X(str, Enum)`) facilita serialização JSON.
#
# As 3 tabelas do Marco 9 (manufacturer, olt_model, onu_model) não usam
# enums, então este módulo está vazio. Os enums de inventory entram a
# partir do Marco 11 (topologia: port_status_enum, pon_type_enum).

from __future__ import annotations
