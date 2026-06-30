# Schema Pydantic de raw_template

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domains.provisioning.enums import (
    TemplateScope,
    TemplateStepFailPolicy,
    TemplateStepPhase,
)


class TemplateParamSpec(BaseModel):
    """Especificação de UM parâmetro esperado em snapshot_params na execução."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["string", "integer", "boolean"]
    required: bool = True


class TemplateStepDef(BaseModel):
    """Definição de UM step do template"""

    model_config = ConfigDict(extra="forbid")

    step_key: str = Field(min_length=1, max_length=64)
    phase: TemplateStepPhase
    command_key: str = Field(min_length=1, max_length=64)
    fail_policy: TemplateStepFailPolicy = TemplateStepFailPolicy.ABORT


class RawTemplate(BaseModel):
    """Forma esperada do JSONB"""

    model_config = ConfigDict(extra="forbid")

    version: str = Field(min_length=1, max_length=32)
    scope: TemplateScope = TemplateScope.ONU_PROVISION
    params_schema: dict[str, TemplateParamSpec] = Field(default_factory=dict)
    steps: list[TemplateStepDef]
    rollback_map: dict[str, str] = Field(default_factory=dict)

    @field_validator("steps")
    @classmethod
    def steps_non_empty(cls, v: list[TemplateStepDef]) -> list[TemplateStepDef]:
        if not v:
            raise ValueError("template precisa ter ao menos 1 step")
        return v

    @field_validator("steps")
    @classmethod
    def step_keys_unique(cls, v: list[TemplateStepDef]) -> list[TemplateStepDef]:
        keys = [s.step_key for s in v]
        if len(keys) != len(set(keys)):
            raise ValueError("step_keys duplicados em steps[]")
        return v

    @model_validator(mode="after")
    def rollback_map_references_existing_steps(self) -> "RawTemplate":  # noqa: UP037
        """Garante que toda chave de rollback_map aparece em steps[].step_key."""

        step_keys = {s.step_key for s in self.steps}
        invalid = sorted(k for k in self.rollback_map if k not in step_keys)
        if invalid:
            raise ValueError(f"rollback_map referencia step_keys inexistentes: {invalid}")
        return self
