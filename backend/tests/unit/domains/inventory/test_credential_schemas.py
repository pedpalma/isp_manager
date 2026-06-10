# Testes unitários dos schemas de Credential.

# Validam o comportamento do Pydantic em isolamento (sem banco). Foco:
# - `model_validator` do `CredentialCreate` rejeita ssh_key sem private_key_ref.
# - `CredentialUpdate` permite payload parcial e NÃO força a regra cruzada (a validação cruzada do PATCH é do service).

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domains.inventory.enums import AuthType
from app.domains.inventory.schemas.credential import (
    CredentialCreate,
    CredentialUpdate,
)


# CredentialCreate: validações positivas
def test_create_password_default_auth_type() -> None:
    obj = CredentialCreate(
        label="Lab Master",
        username="admin",
        secret_ref="ENV_PASS",
    )
    assert obj.auth_type is AuthType.PASSWORD
    assert obj.private_key_ref is None
    assert obj.active is True


def test_create_ssh_key_with_private_key() -> None:
    obj = CredentialCreate(
        label="Lab SSH",
        username="admin",
        secret_ref="ENV_PASSPHRASE",
        auth_type=AuthType.SSH_KEY,
        private_key_ref="ENV_PRIVATE_KEY",
    )
    assert obj.auth_type is AuthType.SSH_KEY
    assert obj.private_key_ref == "ENV_PRIVATE_KEY"


def test_create_certificate_does_not_require_private_key() -> None:
    obj = CredentialCreate(
        label="Lab Cert",
        username="admin",
        secret_ref="ENV_SOMETHING",
        auth_type=AuthType.CERTIFICATE,
    )
    assert obj.auth_type is AuthType.CERTIFICATE


# CredentialCreate: validações negativas
def test_create_ssh_key_without_private_key_raises() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CredentialCreate(
            label="Lab SSH",
            username="admin",
            secret_ref="ENV_PASSPHRASE",
            auth_type=AuthType.SSH_KEY,
            # private_key_ref ausente
        )
    msg = str(exc_info.value)
    assert "private_key_ref" in msg


def test_create_empty_label_raises() -> None:
    with pytest.raises(ValidationError):
        CredentialCreate(
            label="",
            username="admin",
            secret_ref="ENV_PASS",
        )


def test_create_missing_secret_ref_raises() -> None:
    with pytest.raises(ValidationError):
        CredentialCreate(  # type: ignore[call-arg]
            label="Lab",
            username="admin",
        )


def test_create_invalid_auth_type_string_raises() -> None:
    with pytest.raises(ValidationError):
        CredentialCreate(
            label="Lab",
            username="admin",
            secret_ref="ENV_PASS",
            auth_type="invalid",  # type: ignore[arg-type]
        )


# CredentialUpdate
def test_update_all_fields_optional() -> None:
    obj = CredentialUpdate()
    dumped = obj.model_dump(exclude_unset=True)
    assert dumped == {}


def test_update_partial_label_only() -> None:
    obj = CredentialUpdate(label="Renamed")
    dumped = obj.model_dump(exclude_unset=True)
    assert dumped == {"label": "Renamed"}


def test_update_does_not_enforce_cross_validation() -> None:
    # No PATCH é permitido enviar SÓ auth_type=ssh_key (sem
    # private_key_ref). A regra cruzada será aplicada no SERVICE
    # depois de mesclar com o estado atual.
    obj = CredentialUpdate(auth_type=AuthType.SSH_KEY)
    assert obj.auth_type is AuthType.SSH_KEY
    assert obj.private_key_ref is None


def test_update_can_clear_private_key_ref_explicitly() -> None:
    # Cliente manda `null` explicitamente: o schema aceita, e o service
    # vai detectar a inconsistência se o auth_type final for ssh_key.
    obj = CredentialUpdate(private_key_ref=None)
    dumped = obj.model_dump(exclude_unset=True)
    assert "private_key_ref" in dumped
    assert dumped["private_key_ref"] is None
