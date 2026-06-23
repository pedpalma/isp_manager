# Mock OltAdapter para desenvolvimento e testes.

# Mock obrigatório em CI. Toda fixture que precisa de OLT usa este adapter.
# Lab real coexiste em dev se houver (.env decide qual instanciar via factory).

# Mecanismo de injeção de dados: dicionario module-level _CANNED indexado por olt_id.
# Testes registram via set_canned_discovery e limpam via clear_canned_discovery.
# Funciona porque os testes rodam com Celery em modo eager (task_always_eager=True),
# então o adapter é executado no mesmo processo do teste.

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.adapters.olt.base import (
    CommandLog,
    DiscoveredOnu,
    DiscoveryResult,
    OltAdapter,
    OltConnectionConfig,
)

# Storage in_process.
# !NÃO USAR EM PROD
_CANNED: dict[UUID, list[dict[str, Any]]] = {}


def set_canned_discovery(olt_id: UUID, items: list[dict[str, Any]]) -> None:
    """Helper de testes: registra o payload que o mock devolverá para está OLT.

    Cada item é um dict com chaves: serial, slot_index, pon_index e opcionalmente
    pon_position, vendor_id e outros campos que o teste queira passar no raw_payload."""

    _CANNED[olt_id] = list(items)


def clear_canned_discovery(olt_id: UUID | None = None) -> None:
    """Limpa payload registrado. Sem argumento, limpa tudo."""
    if olt_id is None:
        _CANNED.clear()
    else:
        _CANNED.pop(olt_id, None)


class MockOltAdapter(OltAdapter):
    def list_unprovisioned_onus(
        self, config: OltConnectionConfig, *, olt_id: UUID
    ) -> DiscoveryResult:
        # config eh deliberadamente ignorado no mock; mantemos a
        # assinatura para honrar o contrato da ABC.
        del config
        raw_items = _CANNED.get(olt_id, [])
        discovered = [
            DiscoveredOnu(
                serial=item["serial"],
                slot_index=int(item["slot_index"]),
                pon_index=int(item["pon_index"]),
                pon_position=item.get("pon_position"),
                vendor_id=item.get("vendor_id"),
                raw_payload=dict(item),
            )
            for item in raw_items
        ]
        logs = [
            CommandLog(
                step_name="list_unprovisioned",
                command_sent="show gpon onu unconfigured",
                output_received=f"<mock> {len(raw_items)} ONUs detectadas",
                parser_status="ok",
                success=True,
                duration_ms=1,
            )
        ]
        return DiscoveryResult(discovered=discovered, command_logs=logs)

    def health(self, config: OltConnectionConfig) -> bool:
        del config
        return True
