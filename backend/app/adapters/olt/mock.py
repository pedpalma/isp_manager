# Mock OltAdapter para desenvolvimento e testes.

# Mock obrigatório em CI. Toda fixture que precisa de OLT usa este adapter.
# Lab real coexiste em dev se houver (.env decide qual instanciar via factory).

# Mecanismo de injeção de dados: dicionario module-level _CANNED indexado por olt_id.
# Testes registram via set_canned_discovery e limpam via clear_canned_discovery.
# Funciona porque os testes rodam com Celery em modo eager (task_always_eager=True),
# então o adapter é executado no mesmo processo do teste.

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.adapters.olt.base import (
    CommandLog,
    DiscoveredOnu,
    DiscoveryResult,
    OltAdapter,
    OltConnectionConfig,
    OnuLocator,
    OnuState,
    OpticalReading,
    OpticalReadingResult,
    ProvisioningPlan,
    ProvisioningResult,
    StepResult,
)

# Storage in_process.
# !NÃO USAR EM PROD
_CANNED: dict[UUID, list[dict[str, Any]]] = {}
# !Canned data para list_optical_readings.
_CANNED_OPTICAL: dict[UUID, list[dict[str, Any]]] = {}
# !Canned data para provision_onu / deprovision_onu.
_CANNED_PROVISIONING: dict[UUID, dict[str, Any]] = {}
# !Canned data para get_onu_state.
_CANNED_ONU_STATE: dict[UUID, dict[str, Any]] = {}


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


def set_canned_optical_readings(olt_id: UUID, readings: list[dict[str, Any]]) -> None:
    """Helper de teste: injeta payload determinístico de leituras ópticas
    para uma OLT. Cada item do dict deve ter ao menos `serial`. Demais
    campos são opcionais (rx_power_dbm, tx_power_dbm, temperature, etc.)."""
    _CANNED_OPTICAL[olt_id] = readings


def clear_canned_optical_readings(olt_id: UUID) -> None:
    _CANNED_OPTICAL.pop(olt_id, None)


def set_canned_provisioning(
    olt_id: UUID,
    steps: list[dict[str, Any]],
    *,
    overall_success: bool | None = None,
) -> None:
    """Helper de teste: injeta o resultado que provision_onu e deprovision_onu
    devolvem para esta OLT.

    Cada item de steps é um dict com chaves opcionais: command_sent,
    output_received, parser_output, success, duration_ms. overall_success, se
    omitido (None), é calculado como all(step.success). Passe overall_success
    explícito para simular um vendor que decide o resultado terminal por conta própria."""
    _CANNED_PROVISIONING[olt_id] = {
        "steps": list(steps),
        "overall_success": overall_success,
    }


def clear_canned_provisioning(olt_id: UUID | None = None) -> None:
    """Limpa provisionamento canned. Sem argumento, limpa tudo."""
    if olt_id is None:
        _CANNED_PROVISIONING.clear()
    else:
        _CANNED_PROVISIONING.pop(olt_id, None)


def set_canned_onu_state(olt_id: UUID, state: dict[str, Any]) -> None:
    """Helper de teste: injeta o OnuState que get_onu_state devolve para esta
    OLT. Chaves: admin_status, operational_status e opcionalmente raw_payload."""
    _CANNED_ONU_STATE[olt_id] = dict(state)


def clear_canned_onu_state(olt_id: UUID | None = None) -> None:
    """Limpa estado canned. Sem argumento, limpa tudo."""
    if olt_id is None:
        _CANNED_ONU_STATE.clear()
    else:
        _CANNED_ONU_STATE.pop(olt_id, None)


class MockOltAdapter(OltAdapter):
    def list_unprovisioned_onus(
        self, config: OltConnectionConfig, *, olt_id: UUID
    ) -> DiscoveryResult:
        # config é deliberadamente ignorado no mock; mantemos a
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

    def list_optical_readings(
        self, config: OltConnectionConfig, *, olt_id: UUID
    ) -> OpticalReadingResult:
        """Implementação do mock. Devolve leituras do _CANNED_OPTICAL[olt_id]
        ou lista vazia. Gera um CommandLog fictício para auditoria do log."""
        raw = _CANNED_OPTICAL.get(olt_id, [])
        readings: list[OpticalReading] = []
        for entry in raw:
            readings.append(
                OpticalReading(
                    serial=entry["serial"],
                    collected_at=entry.get(
                        "collected_at",
                        datetime.now(timezone.utc),  # noqa: UP017
                    ),
                    rx_power_dbm=entry.get("rx_power_dbm"),
                    tx_power_dbm=entry.get("tx_power_dbm"),
                    temperature=entry.get("temperature"),
                    voltage=entry.get("voltage"),
                    bias_current=entry.get("bias_current"),
                    distance_m=entry.get("distance_m"),
                    status=entry.get("status"),
                    raw_payload=entry.get("raw_payload", {}),
                )
            )
        command_log = CommandLog(
            step_name="optical_readings_mock",
            command_sent="show optical readings (mock)",
            output_received=f"mock returned {len(readings)} readings for olt {olt_id}",
            parser_status="ok",
            success=True,
            duration_ms=1,
        )
        return OpticalReadingResult(readings=readings, command_logs=[command_log])

    def provision_onu(
        self, config: OltConnectionConfig, plan: ProvisioningPlan, *, olt_id: UUID
    ) -> ProvisioningResult:
        del config
        return self._run_plan(plan, olt_id)

    def deprovision_onu(
        self, config: OltConnectionConfig, plan: ProvisioningPlan, *, olt_id: UUID
    ) -> ProvisioningResult:
        del config
        return self._run_plan(plan, olt_id)

    def get_onu_state(
        self, config: OltConnectionConfig, locator: OnuLocator, *, olt_id: UUID
    ) -> OnuState:
        del config
        canned = _CANNED_ONU_STATE.get(olt_id)
        if canned is not None:
            return OnuState(
                admin_status=canned.get("admin_status", "active"),
                operational_status=canned.get("operational_status", "online"),
                raw_payload=canned.get("raw_payload", {"mock": True}),
            )
        # Sem canned: sucesso silencioso, mesma postura do list_unprovisioned_onus.
        return OnuState(
            admin_status="active",
            operational_status="online",
            raw_payload={"mock": True, "locator_serial": locator.serial},
        )

    def health(self, config: OltConnectionConfig) -> bool:
        del config
        return True

    def _run_plan(self, plan: ProvisioningPlan, olt_id: UUID) -> ProvisioningResult:
        """Núcleo compartilhado por provision_onu e deprovision_onu.

        Com canned: devolve exatamente os StepResult injetados e o
        overall_success calculado (all(success) quando não for explícito).
        Sem canned: ecoa o plano (um StepResult de sucesso por comando),
        postura equivalente ao sucesso silencioso do list_unprovisioned_onus."""
        canned = _CANNED_PROVISIONING.get(olt_id)
        if canned is not None:
            steps = [
                StepResult(
                    command_sent=s.get("command_sent", ""),
                    output_received=s.get("output_received"),
                    parser_output=s.get("parser_output"),
                    success=s.get("success", True),
                    duration_ms=s.get("duration_ms", 1),
                )
                for s in canned["steps"]
            ]
            overall = canned["overall_success"]
            if overall is None:
                overall = all(s.success for s in steps)
            return ProvisioningResult(steps=steps, overall_success=overall)
        # Sem canned: ecoa cada comando do plano como um passo bem-sucedido.
        steps = [
            StepResult(
                command_sent=cmd.rendered,
                output_received="<mock> ok",
                parser_output=None,
                success=True,
                duration_ms=1,
            )
            for cmd in plan.commands
        ]
        return ProvisioningResult(steps=steps, overall_success=True)
