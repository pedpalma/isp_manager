# Testes unitários de secret masking

from __future__ import annotations

from app.domains.audit.masking import MASK_STRING, SENSITIVE_KEYS, scrub_secrets


def test_scrub_secrets_none_returns_none() -> None:
    assert scrub_secrets(None) is None


def test_scrub_secrets_primitives_pass_through() -> None:
    assert scrub_secrets("plain") == "plain"
    assert scrub_secrets(42) == 42
    assert scrub_secrets(True) is True


def test_scrub_secrets_masks_known_keys_flat_dict() -> None:
    payload = {
        "secret_ref": "OLT_ADMIN_PASS_REF",
        "username": "admin",
        "auth_type": "password",
    }
    scrubbed = scrub_secrets(payload)
    assert scrubbed == {
        "secret_ref": MASK_STRING,
        "username": "admin",
        "auth_type": "password",
    }


def test_scrub_secrets_masks_all_sensitive_keys() -> None:
    payload = {k: f"value-of-{k}" for k in SENSITIVE_KEYS}
    scrubbed = scrub_secrets(payload)
    assert all(v == MASK_STRING for v in scrubbed.values())
    assert set(scrubbed.keys()) == SENSITIVE_KEYS


def test_scrub_secrets_recursive_nested_dict() -> None:
    payload = {
        "credential": {
            "secret_ref": "X",
            "auth_type": "password",
            "meta": {"private_key_ref": "Y", "kind": "ssh"},
        },
        "olt_id": "olt-1",
    }
    scrubbed = scrub_secrets(payload)
    assert scrubbed == {
        "credential": {
            "secret_ref": MASK_STRING,
            "auth_type": "password",
            "meta": {"private_key_ref": MASK_STRING, "kind": "ssh"},
        },
        "olt_id": "olt-1",
    }


def test_scrub_secrets_list_of_dicts() -> None:
    payload = {"items": [{"password": "abc", "user": "u1"}, {"other": "ok"}]}
    scrubbed = scrub_secrets(payload)
    assert scrubbed == {"items": [{"password": MASK_STRING, "user": "u1"}, {"other": "ok"}]}


def test_scrub_secrets_does_not_mutate_original() -> None:
    original = {"password": "abc", "user": "u1"}
    scrubbed = scrub_secrets(original)
    assert original == {"password": "abc", "user": "u1"}
    assert scrubbed == {"password": MASK_STRING, "user": "u1"}


def test_scrub_secrets_is_case_sensitive() -> None:
    payload = {"PASSWORD": "abc", "password": "def"}
    scrubbed = scrub_secrets(payload)
    assert scrubbed == {"PASSWORD": "abc", "password": MASK_STRING}


def test_scrub_secrets_masks_regardless_of_value_type() -> None:
    payload = {
        "password": 12345,
        "token_hash": ["a", "b"],
        "secret_ref": {"nested": True},
    }
    scrubbed = scrub_secrets(payload)
    assert scrubbed == {
        "password": MASK_STRING,
        "token_hash": MASK_STRING,
        "secret_ref": MASK_STRING,
    }
