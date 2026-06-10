# Enums Python espelhando os ENUMs nativos do Postgres do domínio Inventory.

from __future__ import annotations

from enum import Enum


class AuthType(str, Enum):  # noqa: UP042
    """Tipo de autenticação de uma credencial de acesso a equipamento.
    Espelha o tipo nativo `auth_type_enum` do Postgres (DDL.sql).
    - PASSWORD: usuário + senha. `secret_ref` aponta para a senha no cofre.
    - SSH_KEY: usuário + chave privada. `private_key_ref` aponta para a chave; `secret_ref` aponta para a passphrase.
    - CERTIFICATE: autenticação por certificado.
    """

    PASSWORD = "password"
    SSH_KEY = "ssh_key"
    CERTIFICATE = "certificate"
