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
