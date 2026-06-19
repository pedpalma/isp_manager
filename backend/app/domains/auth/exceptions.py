# Exceções do domínio de autenticação.

# Mapeamento semântico
# 404 notfound: recurso inexistente
# 409 conflict: colisão com unicidade existente
# 400 ReferenceInvalid: fk ausente ou em estado inutilizável (grupo inativo)
# 401 AuthenticationError: identidade ausente/invalida (login, token)
# 403 authorizationerror : autenticado porem sem permissão

from __future__ import annotations

from uuid import UUID

from app.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    BadRequestError,
    ConflictError,
    NotFoundError,
)


# user_group
class UserGroupNotFound(NotFoundError):
    def __init__(self, user_group_id: UUID) -> None:
        super().__init__(
            f"Grupo de usuários não encontrado: {user_group_id}.",
            details={"user_group_id": str(user_group_id)},
        )


class UserGroupConflict(ConflictError):
    def __init__(self, name: str) -> None:
        super().__init__(
            f"Já existe um grupo de usuários com o nome '{name}'.",
            details={"name": name},
        )


class UserGroupReferenceInvalid(BadRequestError):
    """Grupo referenciado por um app_user não existe ou está inativa."""

    def __init__(self, user_group_id: UUID) -> None:
        super().__init__(
            f"Grupo de usuários inválido ou inativo: {user_group_id}.",
            details={"user_group_id": str(user_group_id)},
        )


# app_user
class AppUserNotFound(NotFoundError):
    def __init__(self, app_user_id: UUID) -> None:
        super().__init__(
            f"Usuário nâo encontrado: {app_user_id}.",
            details={"app_user_id": str(app_user_id)},
        )


class AppUserUsernameConflict(ConflictError):
    def __init__(self, username: str) -> None:
        super().__init__(
            f"Já existe um usuário com o username '{username}'.",
            details={"username": username},
        )


class AppUserEmailConflict(ConflictError):
    def __init__(self, email: str) -> None:
        super().__init__(
            f"Já existe um usuário com o e-mail '{email}'",
            details={"email": email},
        )


# Autenticação/Sessão
class InvalidCredentials(AuthenticationError):
    """Login com username inexistente, user inativo ou senha errada.
    mensagem genérica para não revelar qual fator falhou."""

    def __init__(self) -> None:
        super().__init__("Credenciais inválidas.")


class InvalidToken(AuthenticationError):
    """Token ausente, malformado, expirado, tipo errado, ou com
    sessão revogada. Mensagem genérica para não expor o erro."""

    def __init__(self) -> None:
        super().__init__("Token de autenticação ausente ou inválido.")


class CurrentPasswordInvalid(AuthenticationError):
    """Troca de senha em que a senha atual informada não confere"""

    def __init__(self) -> None:
        super().__init__("Senha atual incorreta.")


class PermissionDenied(AuthorizationError):
    """Autenticado, porém, sem permissão administrativa para a ação."""

    def _init__(self) -> None:
        super().__init__("Acesso negado: permissão administrativa necessária.")
