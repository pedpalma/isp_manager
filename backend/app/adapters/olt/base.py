# Contrato comum dos adapters de OLT (Fiberhome, ZTE, mock).

# ABC ao invés de Protocol. Razão: Fiberhome e ZTE vão nascer incrementalmente;
# ABC falha na instanciação se um vendor esquecer um método, Protocol deixa passar silencioso.

# Adapter é PURO. Não toca banco de dados nem resolve segredos.
# Recebe OltConnectionConfig já com host/porta/senha em claro
# (resolvidos pelo orquestrador) e devolve DTO tipado.
# Saída crua do equipamento é preservada em DiscoveredOnu.raw_payload e
# em CommandLog.output_received para auditoria.

# A interface é síncrona porque o adapter é chamado dentro do worker
# Celery, que usa sessão sync. Bibliotecas de SSH (paramiko, netmiko)
# também são síncronas por natureza.

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class OltConnectionConfig:
    """Configurações de conexão com a OLT, já com secret em claro.

    resolução do secret_ref acontece no worker, não no adapter.
    Isso mantém o adapter fácil de testar e desacopla a estratégia de cofre."""

    host: str
    port: int
    protocol: str
    username: str
    password: str
    enable_secret: str | None = None
    timeout_seconds: int = 30


@dataclass(frozen=True, slots=True)
class DiscoveredOnu:
    """Uma ONU vista no equipamento sem provisionamento.

    o adapter NÃO sabe sobre pon_pot_id do inventário. Devolve raw index
    (slot_index, pon_index) e o worker resolve para pon_port_id consultando
    o inventor. Se não resolver, a ONU é descartada e o job vira PARTIAL."""

    serial: str
    slot_index: int
    pon_index: int
    pon_position: int | None = None
    vendor_id: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CommandLog:
    """Registro de UM comando enviado a OLT durante a coleta.

    Vira uma linha de collection_log após a execução. O worker é
    quem trunca output_received antes de persistir."""

    step_name: str
    command_sent: str
    output_received: str | None = None
    parser_status: str | None = None
    success: bool = True
    duration_ms: int | None = None


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    """Resultado completo de uma chamada list_unprovisioned_onus.

    Contém as ONUs descobertas e os logs de comando executados."""

    discovered: list[DiscoveredOnu]
    command_logs: list[CommandLog]


class OltAdapter(ABC):
    """Contrato comum  entre vendor adapters e o mock."""

    @abstractmethod
    def list_unprovisioned_onus(
        self, config: OltConnectionConfig, *, olt_id: UUID
    ) -> DiscoveryResult:
        """Lista de ONUs não provisionadas vistas no equipamento.

        olt_id é passado como contexto para logs do adapter,
        não para consulta ao banco (adapter é puro)."""

    @abstractmethod
    def health(self, config: OltConnectionConfig) -> bool:
        """Ping ao equipamento. Serve para checagens proativas."""
