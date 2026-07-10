# Exceções do domínio provisioning (M18a).

# Herdam de app.core.exceptions: NotFoundError (404), ConflictError (409),
# BadRequestError (400), ValidationError (422).

from __future__ import annotations

from uuid import UUID

from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    NotFoundError,
    ValidationError,
)


# provisioning_template
class ProvisioningTemplateNotFound(NotFoundError):
    def __init__(self, provisioning_template_id: UUID) -> None:
        super().__init__(
            f"Template de provisionamento não encontrado: {provisioning_template_id}.",
            details={"provisioning_template_id": str(provisioning_template_id)},
        )


class ProvisioningTemplateConflict(ConflictError):
    def __init__(
        self,
        manufacturer_id: UUID,
        olt_model_id: UUID | None,
        name: str,
        version: str,
    ) -> None:
        super().__init__(
            "Já existe template com mesma combinação de fabricante, modelo, nome e versão.",
            details={
                "manufacturer_id": str(manufacturer_id),
                "olt_model_id": str(olt_model_id) if olt_model_id else None,
                "name": name,
                "version": version,
            },
        )


# normalized_command
class NormalizedCommandNotFound(NotFoundError):
    def __init__(self, normalized_command_id: UUID) -> None:
        super().__init__(
            f"Comando normalizado não encontrado: {normalized_command_id}.",
            details={"normalized_command_id": str(normalized_command_id)},
        )


class NormalizedCommandConflict(ConflictError):
    def __init__(
        self,
        manufacturer_id: UUID,
        olt_model_id: UUID | None,
        command_key: str,
        version_constraint: str | None,
    ) -> None:
        super().__init__(
            "Já existe comando ativo com mesma combinação de fabricante, modelo, "
            "command_key e version_constraint.",
            details={
                "manufacturer_id": str(manufacturer_id),
                "olt_model_id": str(olt_model_id) if olt_model_id else None,
                "command_key": command_key,
                "version_constraint": version_constraint,
            },
        )


# referências cruzadas
class ManufacturerReferenceInvalid(BadRequestError):
    def __init__(self, manufacturer_id: UUID) -> None:
        super().__init__(
            f"Manufacturer inválido ou inativo: {manufacturer_id}.",
            details={"manufacturer_id": str(manufacturer_id)},
        )


class OltModelReferenceInvalid(BadRequestError):
    def __init__(self, olt_model_id: UUID) -> None:
        super().__init__(
            f"OLT model inválido ou inativo: {olt_model_id}.",
            details={"olt_model_id": str(olt_model_id)},
        )


class ManufacturerOltModelMismatch(BadRequestError):
    """Disparado quando olt_model_id pertence a outro manufacturer.

    Validação semântica não imposta pelo DDL. Sem isso, um template
    'Fiberhome com modelo ZTE' seria gravado e quebraria na hora da
    resolução do command_key."""

    def __init__(self, manufacturer_id: UUID, olt_model_id: UUID) -> None:
        super().__init__(
            "olt_model não pertence ao manufacturer informado.",
            details={
                "manufacturer_id": str(manufacturer_id),
                "olt_model_id": str(olt_model_id),
            },
        )


# schema do raw_template
class TemplateSchemaInvalid(ValidationError):
    """Disparado quando raw_template viola o contrato de estrutura.

    422 (validation_error). Pydantic já cobre a forma básica; esta
    exceção é levantada por validações cruzadas no service."""

    def __init__(self, reason: str, details: dict[str, str] | None = None) -> None:
        super().__init__(
            f"raw_template inválido: {reason}",
            details=details or {},
        )


class TemplateScopeMismatch(ValidationError):
    """raw_template.scope diverge de template_scope da coluna.

    Mantém os dois campos consistentes (a coluna é a fonte de filtro;
    o JSONB documenta a intenção)."""

    def __init__(self, column_scope: str, json_scope: str) -> None:
        super().__init__(
            "raw_template.scope diverge de template_scope.",
            details={"template_scope": column_scope, "raw_template_scope": json_scope},
        )


class ProvisioningOrderNotFound(NotFoundError):
    def __init__(self, provisioning_order_id: UUID) -> None:
        super().__init__(
            f"Ordem de provisionamento não encontrada: {provisioning_order_id}.",
            details={"provisioning_order_id": str(provisioning_order_id)},
        )


class ProvisioningOrderIdempotencyConflict(ConflictError):
    def __init__(self, idempotency_key: str) -> None:
        super().__init__(
            f"Já existe ordem com idempotency_key '{idempotency_key}'.",
            details={"idempotency_key": idempotency_key},
        )


class ProvisioningOrderActiveConflict(ConflictError):
    """Cobre uq_prov_order_active_unique do 0007 (índice parcial em onu_id
    WHERE status IN ('pending','validating','running'))."""

    def __init__(self, onu_id: UUID) -> None:
        super().__init__(
            "Já existe ordem ativa para esta ONU (pendente, validando ou executando).",
            details={"onu_id": str(onu_id)},
        )


class ProvisioningTemplateReferenceInvalid(BadRequestError):
    def __init__(self, provisioning_template_id: UUID, *, reason: str) -> None:
        super().__init__(
            f"Template de provisionamento inválido: {reason}.",
            details={
                "provisioning_template_id": str(provisioning_template_id),
                "reason": reason,
            },
        )


class PonPortReferenceInvalid(BadRequestError):
    """Usado quando pon_port não existe OU não pertence à olt_id da ordem."""

    def __init__(self, pon_port_id: UUID, *, reason: str) -> None:
        super().__init__(
            f"pon_port inválida: {reason}.",
            details={"pon_port_id": str(pon_port_id), "reason": reason},
        )


class LineProfileReferenceInvalid(BadRequestError):
    def __init__(self, line_profile_id: UUID, *, reason: str) -> None:
        super().__init__(
            f"line_profile inválido: {reason}.",
            details={"line_profile_id": str(line_profile_id), "reason": reason},
        )


class ServiceProfileReferenceInvalid(BadRequestError):
    def __init__(self, service_profile_id: UUID, *, reason: str) -> None:
        super().__init__(
            f"service_profile inválido: {reason}.",
            details={"service_profile_id": str(service_profile_id), "reason": reason},
        )


class VlanReferenceInvalid(BadRequestError):
    def __init__(self, vlan_id: UUID, *, reason: str) -> None:
        super().__init__(
            f"vlan inválida: {reason}.",
            details={"vlan_id": str(vlan_id), "reason": reason},
        )


class SerialNotRecognized(BadRequestError):
    def __init__(self, serial: str) -> None:
        super().__init__(
            (
                f"Serial não reconhecido: '{serial}'. Serial precisa existir em "
                "onu (viva) ou em pending_onu (state != 'resolved')."
            ),
            details={"serial": serial},
        )


class OnuIndexConflict(BadRequestError):
    """Já existe outra ONU viva na mesma PON usando o onu_index solicitado."""

    def __init__(self, *, pon_port_id: UUID, onu_index: int, existing_onu_id: UUID) -> None:
        super().__init__(
            f"onu_index {onu_index} já está em uso na PON por outra ONU.",
            details={
                "pon_port_id": str(pon_port_id),
                "onu_index": onu_index,
                "existing_onu_id": str(existing_onu_id),
            },
        )


class RetryOfOrderInvalid(BadRequestError):
    """retry_of_order_id inexistente ou apontando para ordem em estado não terminal."""

    def __init__(self, retry_of_order_id: UUID, *, reason: str) -> None:
        super().__init__(
            f"retry_of_order_id inválido: {reason}.",
            details={"retry_of_order_id": str(retry_of_order_id), "reason": reason},
        )


class ProvisioningOrderIdempotencyPayloadMismatch(ConflictError):
    """`idempotency_key` já usada em outra ordem com payload diferente."""

    def __init__(self, idempotency_key: str) -> None:
        super().__init__(
            (
                f"idempotency_key '{idempotency_key}' já foi usada em outra "
                "ordem com payload diferente. Idempotency keys precisam ser "
                "únicos por payload; use um novo key para este request."
            ),
            details={"idempotency_key": idempotency_key},
        )


class ProvisioningOrderNotCancelable(ConflictError):
    """Ordem não está em estado cancelável (só PENDING é cancelável)."""

    def __init__(self, provisioning_order_id: UUID, current_status: str) -> None:
        super().__init__(
            (
                f"Ordem {provisioning_order_id} não pode ser cancelada "
                f"no estado '{current_status}'. Só ordens em 'pending' são "
                "canceláveis; use retry para gerar nova ordem se necessário."
            ),
            details={
                "provisioning_order_id": str(provisioning_order_id),
                "current_status": current_status,
            },
        )


class OltCommandProfileNotFound(NotFoundError):
    def __init__(self, olt_command_profile_id: UUID) -> None:
        super().__init__(
            f"Perfil de comando OLT não encontrado: {olt_command_profile_id}.",
            details={"olt_command_profile_id": str(olt_command_profile_id)},
        )


class OltCommandProfileConflict(ConflictError):
    """Cobre a unicidade TOTAL de uq_olt_command_profile"""

    def __init__(
        self,
        *,
        olt_model_id: UUID,
        firmware_version: str,
        access_protocol: str,
    ) -> None:
        super().__init__(
            "Já existe um perfil de comando OLT com a mesma combinação de "
            "modelo, firmware e protocolo.",
            details={
                "olt_model_id": str(olt_model_id),
                "firmware_version": firmware_version,
                "access_protocol": access_protocol,
            },
        )
