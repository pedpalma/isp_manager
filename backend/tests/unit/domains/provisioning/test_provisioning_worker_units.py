# Testes unitários das funções puras do provisioning_worker.

# Escopo: apenas funções que NÃO tocam o banco. Truncamento, rendering,
# packing de rollback, versão-match e _snapshot_missing_required. Fluxos
# transacionais (fase 1/3/4) exigem fixtures de banco e vão nos testes de
# integração.

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.adapters.olt.base import PlannedCommand, StepResult
from app.domains.provisioning.services.provisioning_worker import (
    MAX_OUTPUT_LENGTH,
    _pack_rollback_commands,
    _render_command,
    _row_version_matches,
    _snapshot_missing_required,
    _truncate,
    _ValidationFailure,
)

# _truncate


class TestTruncate:
    def test_none_stays_none(self) -> None:
        assert _truncate(None) is None

    def test_short_string_unchanged(self) -> None:
        assert _truncate("abc") == "abc"

    def test_exactly_max_unchanged(self) -> None:
        val = "x" * MAX_OUTPUT_LENGTH
        assert _truncate(val) == val

    def test_over_max_truncated_with_suffix(self) -> None:
        val = "x" * (MAX_OUTPUT_LENGTH + 100)
        out = _truncate(val)
        assert out is not None
        assert out.startswith("x" * 100)  # começa com Xs
        assert out.endswith("[output truncated]")
        # tamanho = MAX + suffix; NÃO trunca o suffix
        assert len(out) == MAX_OUTPUT_LENGTH + len("\n... [output truncated]")


# _render_command


class TestRenderCommand:
    def test_basic_substitution_from_snapshot(self) -> None:
        rendered = _render_command(
            template_string="show onu {onu_index}",
            snapshot={"onu_index": 5},
            command_vars={},
        )
        assert rendered == "show onu 5"

    def test_command_vars_provides_defaults(self) -> None:
        rendered = _render_command(
            template_string="set {mode} onu {onu_index}",
            snapshot={"onu_index": 7},
            command_vars={"mode": "auto"},
        )
        assert rendered == "set auto onu 7"

    def test_snapshot_overrides_command_vars(self) -> None:
        """snapshot_params vem por último no update; deve sobrescrever
        command_vars em caso de colisão."""
        rendered = _render_command(
            template_string="set {mode}",
            snapshot={"mode": "manual"},
            command_vars={"mode": "auto"},
        )
        assert rendered == "set manual"

    def test_missing_variable_raises_validation_failure(self) -> None:
        with pytest.raises(_ValidationFailure) as excinfo:
            _render_command(
                template_string="show onu {vlan_number}",
                snapshot={"onu_index": 5},
                command_vars={},
            )
        assert "vlan_number" in str(excinfo.value)

    def test_no_placeholders_returns_template_verbatim(self) -> None:
        rendered = _render_command(
            template_string="show onu detail",
            snapshot={"onu_index": 5},
            command_vars={},
        )
        assert rendered == "show onu detail"


# _row_version_matches


class TestRowVersionMatches:
    def test_both_null_matches(self) -> None:
        assert _row_version_matches(None, None) is True

    def test_row_null_matches_any(self) -> None:
        # Comando manufacturer-wide sem versão bate com qualquer requisição.
        assert _row_version_matches(None, "1.2") is True

    def test_requested_null_matches_any(self) -> None:
        # Requisição sem constraint aceita qualquer versão do catálogo.
        assert _row_version_matches("1.2", None) is True

    def test_both_present_and_equal_matches(self) -> None:
        assert _row_version_matches("1.2", "1.2") is True

    def test_both_present_and_different_does_not_match(self) -> None:
        assert _row_version_matches("1.2", "2.0") is False


# _snapshot_missing_required


class TestSnapshotMissingRequired:
    def _order(self, snapshot: dict) -> object:
        # Objeto duck-typed com apenas snapshot_params.
        return SimpleNamespace(snapshot_params=snapshot)

    def test_no_params_schema_no_missing(self) -> None:
        order = self._order({"onu_index": 5})
        result = _snapshot_missing_required(order, {})  # type: ignore[arg-type]
        assert result == []

    def test_all_required_present(self) -> None:
        order = self._order({"onu_index": 5, "vlan_id": str(uuid4())})
        raw = {
            "params_schema": {
                "onu_index": {"type": "int", "required": True},
                "vlan_id": {"type": "uuid", "required": True},
            }
        }
        assert _snapshot_missing_required(order, raw) == []  # type: ignore[arg-type]

    def test_missing_required_returned(self) -> None:
        order = self._order({"onu_index": 5})
        raw = {
            "params_schema": {
                "onu_index": {"type": "int", "required": True},
                "vlan_id": {"type": "uuid", "required": True},
            }
        }
        assert _snapshot_missing_required(order, raw) == ["vlan_id"]  # type: ignore[arg-type]

    def test_optional_missing_not_returned(self) -> None:
        order = self._order({})
        raw = {
            "params_schema": {
                "external_customer_id": {"type": "str", "required": False},
            }
        }
        assert _snapshot_missing_required(order, raw) == []  # type: ignore[arg-type]

    def test_non_dict_spec_ignored(self) -> None:
        """Robustez: se params_schema tem entrada mal-formada, ignora
        silenciosamente em vez de estourar. Ingest da API já garante a forma."""
        order = self._order({})
        raw = {
            "params_schema": {
                "onu_index": "int",  # forma antiga/errada
            }
        }
        assert _snapshot_missing_required(order, raw) == []  # type: ignore[arg-type]

    def test_snapshot_none_treated_as_empty(self) -> None:
        order = SimpleNamespace(snapshot_params=None)
        raw = {"params_schema": {"onu_index": {"type": "int", "required": True}}}
        assert _snapshot_missing_required(order, raw) == ["onu_index"]  # type: ignore[arg-type]


# _pack_rollback_commands


class TestPackRollbackCommands:
    def _planned(self, command_key: str) -> PlannedCommand:
        return PlannedCommand(
            command_key=command_key,
            rendered=f"rendered:{command_key}",
            timeout_ms=5000,
        )

    def test_empty_input_returns_empty_list(self) -> None:
        assert _pack_rollback_commands([], []) == []

    def test_serializes_step_result(self) -> None:
        # command_key vem do PlannedCommand original (correlação por posição).
        planned = [self._planned("unauthorize-onu")]
        steps = [
            StepResult(
                command_sent="no gpon onu 5",
                output_received="ok",
                success=True,
                duration_ms=812,
                parser_output={},
            )
        ]
        packed = _pack_rollback_commands(planned, steps)
        assert len(packed) == 1
        entry = packed[0]
        assert entry["step_key"] == "unauthorize-onu"
        assert entry["command_sent"] == "no gpon onu 5"
        assert entry["output_received"] == "ok"
        assert entry["success"] is True
        assert entry["duration_ms"] == 812

    def test_truncates_long_outputs(self) -> None:
        planned = [self._planned("delete-onu")]
        long_output = "y" * (MAX_OUTPUT_LENGTH + 500)
        steps = [
            StepResult(
                command_sent="del onu 1",
                output_received=long_output,
                success=False,
                duration_ms=None,
                parser_output=None,
            )
        ]
        packed = _pack_rollback_commands(planned, steps)
        assert packed[0]["output_received"] is not None
        assert packed[0]["output_received"].endswith("[output truncated]")
        assert packed[0]["duration_ms"] is None

    def test_preserves_order(self) -> None:
        planned = [self._planned(f"cmd-{i}") for i in range(3)]
        steps = [
            StepResult(
                command_sent=f"cmd {i}",
                output_received="ok",
                success=True,
                duration_ms=100,
                parser_output={},
            )
            for i in range(3)
        ]
        packed = _pack_rollback_commands(planned, steps)
        assert [p["step_key"] for p in packed] == ["cmd-0", "cmd-1", "cmd-2"]

    def test_excess_step_results_get_synthetic_step_key(self) -> None:
        """Invariante defensiva: se o adapter devolver MAIS StepResult do
        que PlannedCommand (não deveria acontecer), os excedentes recebem
        step_key sintético em vez de estourar IndexError."""
        planned = [self._planned("cmd-0")]  # só um planejado
        steps = [
            StepResult(command_sent="a", success=True, duration_ms=1, parser_output={}),
            StepResult(command_sent="b", success=True, duration_ms=2, parser_output={}),
        ]
        packed = _pack_rollback_commands(planned, steps)
        assert packed[0]["step_key"] == "cmd-0"
        assert packed[1]["step_key"] == "__pos_1__"
