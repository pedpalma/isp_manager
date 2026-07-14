# Testes unitários dos enums de auditoria

from __future__ import annotations

from app.domains.audit.enums import AuditAction, AuditResult


def test_audit_action_values_follow_dotted_convention() -> None:
    for action in AuditAction:
        assert "." in action.value, f"{action.name}={action.value!r} sem ponto"
        assert action.value == action.value.strip()


def test_audit_action_no_duplicated_values() -> None:
    values = [a.value for a in AuditAction]
    assert len(values) == len(set(values))


def test_audit_action_is_str_enum() -> None:
    assert isinstance(AuditAction.OLT_SOFT_DELETED, str)
    assert AuditAction.OLT_SOFT_DELETED == "olt.soft_deleted"


def test_audit_result_values() -> None:
    assert AuditResult.SUCCESS.value == "success"
    assert AuditResult.FAILURE.value == "failure"
    assert AuditResult.PARTIAL.value == "partial"


def test_audit_result_is_str_enum() -> None:
    assert isinstance(AuditResult.SUCCESS, str)
    assert AuditResult.SUCCESS == "success"
