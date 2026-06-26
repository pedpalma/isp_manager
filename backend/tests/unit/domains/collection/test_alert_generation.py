# Testes unit da logica de detecção de violação usada no worker.
# Sem DB. Foco em casos de borda da função _check_violation.

from __future__ import annotations

from app.domains.collection.services.signal_reading_worker import _check_violation


def test_violation_below_min():
    assert _check_violation(-31.0, -30.0, -8.0) is True


def test_violation_above_max():
    assert _check_violation(-5.0, -30.0, -8.0) is True


def test_no_violation_within_range():
    assert _check_violation(-15.0, -30.0, -8.0) is False


def test_boundary_min_is_not_violation():
    # exatamente no limite mínimo NÃO é violação (>=)
    assert _check_violation(-30.0, -30.0, -8.0) is False


def test_boundary_max_is_not_violation():
    # exatamente no limite máximo NÃO é violação (<=)
    assert _check_violation(-8.0, -30.0, -8.0) is False


def test_only_min_threshold():
    # só threshold_min definido
    assert _check_violation(-31.0, -30.0, None) is True
    assert _check_violation(-25.0, -30.0, None) is False


def test_only_max_threshold():
    # só threshold_max definido
    assert _check_violation(85.0, None, 80.0) is True
    assert _check_violation(60.0, None, 80.0) is False


def test_no_thresholds_no_violation():
    # configuração inválida do ponto de vista do DDL,
    # mas a função em sí não deve quebrar.
    assert _check_violation(0.0, None, None) is False
