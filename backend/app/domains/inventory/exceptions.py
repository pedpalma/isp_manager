# Exceções específicas do domínio Inventory.

from __future__ import annotations

from uuid import UUID

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError


# Manufacturer
class ManufacturerNotFound(NotFoundError):
    def __init__(self, manufacturer_id: UUID) -> None:
        super().__init__(
            f"Fabricante não encontrado: {manufacturer_id}.",
            details={"manufacturer_id": str(manufacturer_id)},
        )


class ManufacturerSlugConflict(ConflictError):
    def __init__(self, slug: str) -> None:
        super().__init__(
            f"Já existe um fabricante com slug '{slug}'.",
            details={"slug": slug},
        )


# OltModel
class OltModelNotFound(NotFoundError):
    def __init__(self, olt_model_id: UUID) -> None:
        super().__init__(
            f"Modelo de OLT não encontrado: {olt_model_id}.",
            details={"olt_model_id": str(olt_model_id)},
        )


class OltModelConflict(ConflictError):
    def __init__(self, manufacturer_id: UUID, model: str) -> None:
        super().__init__(
            f"Já existe um modelo de OLT '{model}' para este fabricante.",
            details={
                "manufacturer_id": str(manufacturer_id),
                "model": model,
            },
        )


# OnuModel
class OnuModelNotFound(NotFoundError):
    def __init__(self, onu_model_id: UUID) -> None:
        super().__init__(
            f"Modelo de ONU não encontrado: {onu_model_id}.",
            details={"onu_model_id": str(onu_model_id)},
        )


class OnuModelConflict(ConflictError):
    def __init__(self, manufacturer_id: UUID, model: str) -> None:
        super().__init__(
            f"Já existe um modelo de ONU '{model}' para este fabricante.",
            details={
                "manufacturer_id": str(manufacturer_id),
                "model": model,
            },
        )


class OnuModelVendorIdConflict(ConflictError):
    def __init__(self, manufacturer_id: UUID, vendor_id: str) -> None:
        super().__init__(
            f"Já existe um modelo de ONU com vendor_id '{vendor_id}' para este fabricante.",
            details={
                "manufacturer_id": str(manufacturer_id),
                "vendor_id": vendor_id,
            },
        )


# Credential
class CredentialNotFound(NotFoundError):
    def __init__(self, credential_id: UUID) -> None:
        super().__init__(
            f"Credencial não encontrada: {credential_id}.",
            details={"credential_id": str(credential_id)},
        )


class CredentialAuthMismatch(ConflictError):
    def __init__(self, credential_id: UUID, auth_type: str) -> None:
        super().__init__(
            ("Estado inconsistente: auth_type='ssh_key' exige private_key_ref preenchido."),
            details={
                "credential_id": str(credential_id),
                "auth_type": auth_type,
            },
        )


class CredentialInUse(ConflictError):
    """Não desativar credencial vinculada a OLT viva. 409, porque colide com o estado atual do inventário."""

    def __init__(self, credential_id: UUID) -> None:
        super().__init__(
            "Não é possível desativar: a credencial está em uso por ao menos uma OLT ativa.",
            details={"credential_id": str(credential_id)},
        )


# OLT
class OltNotFound(NotFoundError):
    def __init__(self, olt_id: UUID) -> None:
        super().__init__(
            f"OLT não encontrada: {olt_id}.",
            details={"olt_id": str(olt_id)},
        )


class OltNameConflict(ConflictError):
    def __init__(self, name: str) -> None:
        super().__init__(
            f"Já existe uma OLT ativa com o nome '{name}'.",
            details={"name": name},
        )


class OltAddressConflict(ConflictError):
    def __init__(self, ip: str, management_port: int) -> None:
        super().__init__(
            f"Já existe uma OLT ativa em {ip}:{management_port}.",
            details={"ip": ip, "management_port": management_port},
        )


class OltModelReferenceInvalid(BadRequestError):
    """olt_model_id informado não existe. 400 (referência inválida), não 404,
    porque a OLT em si não foi solicitada: o pedido de criação está malformado."""

    def __init__(self, olt_model_id: UUID) -> None:
        super().__init__(
            f"olt_model_id inválido: modelo não encontrado ({olt_model_id}).",
            details={"olt_model_id": str(olt_model_id)},
        )


class CredentialReferenceInvalid(BadRequestError):
    """credential_id informado não existe."""

    def __init__(self, credential_id: UUID) -> None:
        super().__init__(
            f"credential_id inválido: credencial não encontrada ({credential_id}).",
            details={"credential_id": str(credential_id)},
        )


class CredentialInactive(BadRequestError):
    """credential_id existe, mas está inativa. Não pode vincular a uma OLT."""

    def __init__(self, credential_id: UUID) -> None:
        super().__init__(
            f"credential_id inválido: a credencial está inativa ({credential_id}).",
            details={"credential_id": str(credential_id)},
        )
