# Testes do schema Pydantic RawTemplate (M18a).

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domains.provisioning.schemas.raw_template import RawTemplate


def _base_template_dict() -> dict:
    return {
        "version": "1",
        "scope": "onu_provision",
        "params_schema": {
            "serial": {"type": "string", "required": True},
        },
        "steps": [
            {
                "step_key": "authorize_onu",
                "phase": "execute",
                "command_key": "authorize_onu",
                "fail_policy": "abort",
            }
        ],
        "rollback_map": {"authorize_onu": "deauthorize_onu"},
    }


def test_valid_template_parses():
    tmpl = RawTemplate.model_validate(_base_template_dict())
    assert tmpl.version == "1"
    assert tmpl.scope.value == "onu_provision"
    assert len(tmpl.steps) == 1
    assert tmpl.steps[0].step_key == "authorize_onu"


def test_default_scope_is_onu_provision():
    payload = _base_template_dict()
    del payload["scope"]
    tmpl = RawTemplate.model_validate(payload)
    assert tmpl.scope.value == "onu_provision"


def test_default_fail_policy_is_abort():
    payload = _base_template_dict()
    del payload["steps"][0]["fail_policy"]
    tmpl = RawTemplate.model_validate(payload)
    assert tmpl.steps[0].fail_policy.value == "abort"


def test_empty_steps_rejected():
    payload = _base_template_dict()
    payload["steps"] = []
    with pytest.raises(ValidationError) as exc_info:
        RawTemplate.model_validate(payload)
    assert "1 step" in str(exc_info.value) or "step" in str(exc_info.value).lower()


def test_duplicate_step_keys_rejected():
    payload = _base_template_dict()
    payload["steps"].append(
        {
            "step_key": "authorize_onu",
            "phase": "execute",
            "command_key": "x",
            "fail_policy": "abort",
        }
    )
    with pytest.raises(ValidationError) as exc_info:
        RawTemplate.model_validate(payload)
    assert "duplicad" in str(exc_info.value).lower()


def test_rollback_map_references_nonexistent_step_rejected():
    payload = _base_template_dict()
    payload["rollback_map"] = {"step_que_nao_existe": "deauthorize"}
    with pytest.raises(ValidationError) as exc_info:
        RawTemplate.model_validate(payload)
    assert "rollback_map" in str(exc_info.value).lower()


def test_invalid_phase_rejected():
    payload = _base_template_dict()
    payload["steps"][0]["phase"] = "morpheus"
    with pytest.raises(ValidationError):
        RawTemplate.model_validate(payload)


def test_extra_field_in_step_rejected():
    # Modelo Pydantic com extra="forbid".
    payload = _base_template_dict()
    payload["steps"][0]["unknown_field"] = "boom"
    with pytest.raises(ValidationError):
        RawTemplate.model_validate(payload)
