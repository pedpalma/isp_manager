from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domains.inventory.schemas.chassis import (
    ChassisCreate,
    ChassisUpdate,
)


class TestChassisCreate:
    def test_minimal_payload_accepted(self) -> None:
        payload = ChassisCreate(olt_id=uuid4(), chassis_index=0)
        assert payload.chassis_index == 0
        assert payload.description is None

    def test_chassis_index_rejects_negative(self) -> None:
        with pytest.raises(ValidationError):
            ChassisCreate(olt_id=uuid4(), chassis_index=-1)

    def test_description_max_length(self) -> None:
        with pytest.raises(ValidationError):
            ChassisCreate(
                olt_id=uuid4(),
                chassis_index=0,
                description="x" * 300,
            )


class TestChassisUpdate:
    def test_update_only_has_description(self) -> None:
        # olt_id e chassis_index são imutáveis: não aparecem como campos.
        fields = set(ChassisUpdate.model_fields.keys())
        assert fields == {"description"}

    def test_update_accepts_null_to_clear(self) -> None:
        payload = ChassisUpdate(description=None)
        dumped = payload.model_dump(exclude_unset=False)
        assert dumped == {"description": None}
