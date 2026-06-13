from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domains.inventory.enums import PortStatus
from app.domains.inventory.schemas.slot import SlotCreate, SlotUpdate


class TestSlotCreate:
    def test_minimal_payload(self) -> None:
        payload = SlotCreate(chassis_id=uuid4(), slot_index=0)
        assert payload.board_type is None

    def test_status_not_in_create(self) -> None:
        # status é preenchido pelo DEFAULT do banco; não está no Create.
        assert "status" not in SlotCreate.model_fields

    def test_slot_index_rejects_negative(self) -> None:
        with pytest.raises(ValidationError):
            SlotCreate(chassis_id=uuid4(), slot_index=-1)


class TestSlotUpdate:
    def test_chassis_id_is_immutable(self) -> None:
        fields = set(SlotUpdate.model_fields.keys())
        assert "chassis_id" not in fields
        assert "slot_index" not in fields
        assert "board_type" in fields
        assert "status" in fields

    def test_status_optional(self) -> None:
        # A validação é responsabilidade do service.
        # O schema aceita qualquer PortStatus.
        for s in PortStatus:
            payload = SlotUpdate(status=s)
            assert payload.status == s
