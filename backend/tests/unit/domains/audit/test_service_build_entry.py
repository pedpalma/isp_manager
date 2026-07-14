# Testes unitários para construção de AuditLog

from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.actor import Actor, system_actor
from app.core.logging import bind_request_id, clear_request_context
from app.domains.audit.enums import AuditAction, AuditResult
from app.domains.audit.masking import MASK_STRING
from app.domains.audit.services.audit_log import _build_entry


@pytest.fixture(autouse=True)
def _reset_request_context():
    """Cada testes começa com o contexto limpo e o limpa ao final."""
    clear_request_context()
    yield
    clear_request_context()


def _make_human_actor() -> Actor:
    return Actor(actor_id=uuid4(), username="pytest-admin", is_system=False)


def test_build_entry_system_actor_leaves_app_user_is_null() -> None:
    entity_id = uuid4()
    entry = _build_entry(
        actor=system_actor(),
        action=AuditAction.OLT_SOFT_DELETED,
        result=AuditResult.SUCCESS,
        entity_type="olt",
        entity_id=entity_id,
        olt_id=entity_id,
        onu_id=None,
        provisioning_order_id=None,
        error_detail=None,
        before=None,
        after=None,
        extra=None,
    )

    assert entry.app_user_id is None
    assert entry.event_metadata is not None
    assert entry.event_metadata["actor_is_system"] is True
    assert entry.action == "olt.soft_deleted"
    assert entry.result == "success"
    assert entry.entity_type == "olt"
    assert entry.entity_id == entity_id
    assert entry.olt_id == entity_id


def test_build_entry_human_actor_fills_app_user_id() -> None:
    actor = _make_human_actor()
    entity_id = uuid4()

    entry = _build_entry(
        actor=actor,
        action=AuditAction.CREDENTIAL_UPDATED,
        result=AuditResult.SUCCESS,
        entity_type="credential",
        entity_id=entity_id,
        olt_id=None,
        onu_id=None,
        provisioning_order_id=None,
        error_detail=None,
        before=None,
        after=None,
        extra=None,
    )

    assert entry.app_user_id == actor.actor_id
    assert entry.event_metadata is not None
    assert entry.event_metadata["actor_is_system"] is False
    assert entry.event_metadata["actor_username"] == "pytest-admin"


def test_build_entry_scrubs_secrets_in_before_and_after() -> None:
    actor = _make_human_actor()
    entry = _build_entry(
        actor=actor,
        action=AuditAction.CREDENTIAL_UPDATED,
        result=AuditResult.SUCCESS,
        entity_type="credential",
        entity_id=uuid4(),
        olt_id=None,
        onu_id=None,
        provisioning_order_id=None,
        error_detail=None,
        before={"secret_ref": "OLD_REF", "auth_type": "password"},
        after={"secret_ref": "NEW_REF", "auth_type": "password"},
        extra={"password": "must_be_masked", "unrelated": "ok"},
    )

    assert entry.before_data == {"secret_ref": MASK_STRING, "auth_type": "password"}
    assert entry.after_data == {"secret_ref": MASK_STRING, "auth_type": "password"}
    assert entry.event_metadata is not None
    assert entry.event_metadata["password"] == MASK_STRING
    assert entry.event_metadata["unrelated"] == "ok"


def test_build_entry_captures_request_id_from_context() -> None:
    bind_request_id("test-req-id-123")

    entry = _build_entry(
        actor=system_actor(),
        action=AuditAction.COLLECTION_JOB_CREATED,
        result=AuditResult.SUCCESS,
        entity_type="collection_job",
        entity_id=uuid4(),
        olt_id=None,
        onu_id=None,
        provisioning_order_id=None,
        error_detail=None,
        before=None,
        after=None,
        extra=None,
    )

    assert entry.request_id == "test-req-id-123"


def test_build_entry_request_id_null_when_context_clean() -> None:
    entry = _build_entry(
        actor=system_actor(),
        action=AuditAction.COLLECTION_JOB_CREATED,
        result=AuditResult.SUCCESS,
        entity_type="collection_job",
        entity_id=uuid4(),
        olt_id=None,
        onu_id=None,
        provisioning_order_id=None,
        error_detail=None,
        before=None,
        after=None,
        extra=None,
    )
    assert entry.request_id is None


def test_build_entry_error_detail_passthrough() -> None:
    entry = _build_entry(
        actor=system_actor(),
        action=AuditAction.PROVISIONING_ORDER_FINISHED,
        result=AuditResult.FAILURE,
        entity_type="provisioning_order",
        entity_id=uuid4(),
        olt_id=None,
        onu_id=None,
        provisioning_order_id=uuid4(),
        error_detail="phase3: adapter falhou",
        before=None,
        after=None,
        extra=None,
    )
    assert entry.error_detail == "phase3: adapter falhou"
    assert entry.result == "failure"


def test_build_entry_extra_does_not_override_actor_fields() -> None:
    actor = _make_human_actor()
    entry = _build_entry(
        actor=actor,
        action=AuditAction.AUTH_LOGIN,
        result=AuditResult.SUCCESS,
        entity_type="app_user",
        entity_id=uuid4(),
        olt_id=None,
        onu_id=None,
        provisioning_order_id=None,
        error_detail=None,
        before=None,
        after=None,
        extra={"actor_username": "override-name", "custom": "data"},
    )
    assert entry.event_metadata is not None
    assert entry.event_metadata["actor_username"] == "override-name"
    assert entry.event_metadata["custom"] == "data"
