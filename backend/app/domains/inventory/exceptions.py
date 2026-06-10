# Exceções específicas do domínio Inventory.

from __future__ import annotations

from uuid import UUID

from app.core.exceptions import ConflictError, NotFoundError


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
