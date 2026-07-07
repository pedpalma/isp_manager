# Testes unitários do EnvSecretStore

from __future__ import annotations

import os

import pytest

from app.adapters.secrets.env_store import EnvSecretStore
from app.core.exceptions import ConfigurationError


def test_resolves_existing_env_var(monkeypatch):
    monkeypatch.setenv("PYTEST_SECRET_OK", "hello-world")
    assert EnvSecretStore().resolve("PYTEST_SECRET_OK") == "hello-world"


def test_missing_env_var_raises_configuration_error(monkeypatch):
    monkeypatch.delenv("PYTEST_SECRET_MISSING", raising=False)
    with pytest.raises(ConfigurationError) as exc:
        EnvSecretStore().resolve("PYTEST_SECRET_MISSING")
    assert "PYTEST_SECRET_MISSING" in str(exc.value)


def test_empty_env_var_raises(monkeypatch):
    monkeypatch.setenv("PYTEST_SECRET_EMPTY", "")
    with pytest.raises(ConfigurationError):
        EnvSecretStore().resolve("PYTEST_SECRET_EMPTY")


def test_empty_ref_raises():
    with pytest.raises(ConfigurationError):
        EnvSecretStore().resolve("")


def test_whitespace_ref_raises():
    with pytest.raises(ConfigurationError):
        EnvSecretStore().resolve("   ")


@pytest.mark.parametrize(
    "ref",
    ["bad/name", "bad\\name", "bad'name", 'bad"name', "bad\nname"],
)
def test_forbidden_chars_raise(ref):
    with pytest.raises(ConfigurationError):
        EnvSecretStore().resolve(ref)


def test_non_string_ref_raises():
    with pytest.raises(ConfigurationError):
        EnvSecretStore().resolve(123)  # type: ignore[arg-type]


def test_trims_whitespace_around_ref(monkeypatch):
    monkeypatch.setenv("PYTEST_TRIM", "abc")
    assert EnvSecretStore().resolve("  PYTEST_TRIM  ") == "abc"
    # Cleanup
    if "PYTEST_TRIM" in os.environ:
        os.environ.pop("PYTEST_TRIM", None)
