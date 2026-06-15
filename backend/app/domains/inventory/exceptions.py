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


# Chassis (Marco 12)
class ChassisNotFound(NotFoundError):
    def __init__(self, chassis_id: UUID) -> None:
        super().__init__(
            f"Chassis não encontrado: {chassis_id}.",
            details={"chassis_id": str(chassis_id)},
        )


class ChassisConflict(ConflictError):
    """Unicidade (olt_id, chassis_index) violada."""

    def __init__(self, olt_id: UUID, chassis_index: int) -> None:
        super().__init__(
            f"Já existe um chassis com índice {chassis_index} para esta OLT.",
            details={
                "olt_id": str(olt_id),
                "chassis_index": chassis_index,
            },
        )


class OltReferenceInvalid(BadRequestError):
    """olt_id informado não existe ou está soft-deleted."""

    def __init__(self, olt_id: UUID) -> None:
        super().__init__(
            f"olt_id inválido: OLT não encontrada ou inativada ({olt_id}).",
            details={"olt_id": str(olt_id)},
        )


# Slot
class SlotNotFound(NotFoundError):
    def __init__(self, slot_id: UUID) -> None:
        super().__init__(
            f"Slot não encontrado: {slot_id}.",
            details={"slot_id": str(slot_id)},
        )


class SlotConflict(ConflictError):
    """Unicidade (chassis_id, slot_index) violada."""

    def __init__(self, chassis_id: UUID, slot_index: int) -> None:
        super().__init__(
            f"Já existe um slot com índice {slot_index} para este chassis.",
            details={
                "chassis_id": str(chassis_id),
                "slot_index": slot_index,
            },
        )


class ChassisReferenceInvalid(BadRequestError):
    """chassis_id informado não existe ou pertence a OLT soft-deleted."""

    def __init__(self, chassis_id: UUID) -> None:
        super().__init__(
            f"chassis_id inválido: chassis não encontrado ou OLT pai inativada ({chassis_id}).",
            details={"chassis_id": str(chassis_id)},
        )


class SlotStatusInvalid(BadRequestError):
    """Tentativa de setar status fora do conjunto admissível pela aplicação."""

    def __init__(self, requested: str, allowed: list[str]) -> None:
        super().__init__(
            (
                f"status='{requested}' não pode ser definido manualmente. "
                f"Valores aceitos pela aplicação: {allowed}."
            ),
            details={"requested": requested, "allowed": allowed},
        )


# PonPort
class PonPortNotFound(NotFoundError):
    def __init__(self, pon_port_id: UUID) -> None:
        super().__init__(
            f"Porta PON não encontrada: {pon_port_id}.",
            details={"pon_port_id": str(pon_port_id)},
        )


class PonPortConflict(ConflictError):
    """Unicidade (slot_id, pon_index) violada."""

    def __init__(self, slot_id: UUID, pon_index: int) -> None:
        super().__init__(
            f"Já existe uma porta PON com índice {pon_index} para este slot.",
            details={
                "slot_id": str(slot_id),
                "pon_index": pon_index,
            },
        )


class SlotReferenceInvalid(BadRequestError):
    """slot_id informado não existe ou pertence a OLT soft-deleted."""

    def __init__(self, slot_id: UUID) -> None:
        super().__init__(
            f"slot_id inválido: slot não encontrado ou OLT pai inativada ({slot_id}).",
            details={"slot_id": str(slot_id)},
        )


class PonPortStatusInvalid(BadRequestError):
    """Tentativa de setar status fora do conjunto admissível pela aplicação."""

    def __init__(self, requested: str, allowed: list[str]) -> None:
        super().__init__(
            (
                f"status='{requested}' não pode ser definido manualmente. "
                f"Valores aceitos pela aplicação: {allowed}."
            ),
            details={"requested": requested, "allowed": allowed},
        )


# Vlan
class VlanNotFound(NotFoundError):
    def __init__(self, vlan_id: UUID) -> None:
        super().__init__(
            f"VLAN nao encontrada: {vlan_id}.",
            details={"vlan_id": str(vlan_id)},
        )


class VlanConflict(ConflictError):
    """Unicidade (olt_id, vlan_number) violada. TOTAL: desativar nao libera o numero."""

    def __init__(self, olt_id: UUID, vlan_number: int) -> None:
        super().__init__(
            f"Ja existe a VLAN {vlan_number} nesta OLT.",
            details={"olt_id": str(olt_id), "vlan_number": vlan_number},
        )


# LineProfile
class LineProfileNotFound(NotFoundError):
    def __init__(self, line_profile_id: UUID) -> None:
        super().__init__(
            f"Perfil de linha nao encontrado: {line_profile_id}.",
            details={"line_profile_id": str(line_profile_id)},
        )


class LineProfileConflict(ConflictError):
    """Unicidade (olt_id, name, version) violada."""

    def __init__(self, olt_id: UUID, name: str, version: str) -> None:
        super().__init__(
            f"Ja existe o perfil de linha '{name}' versao '{version}' nesta OLT.",
            details={"olt_id": str(olt_id), "name": name, "version": version},
        )


# ServiceProfile
class ServiceProfileNotFound(NotFoundError):
    def __init__(self, service_profile_id: UUID) -> None:
        super().__init__(
            f"Perfil de servico nao encontrado: {service_profile_id}.",
            details={"service_profile_id": str(service_profile_id)},
        )


class ServiceProfileConflict(ConflictError):
    """Unicidade (olt_id, name, version) violada."""

    def __init__(self, olt_id: UUID, name: str, version: str) -> None:
        super().__init__(
            f"Ja existe o perfil de servico '{name}' versao '{version}' nesta OLT.",
            details={"olt_id": str(olt_id), "name": name, "version": version},
        )
