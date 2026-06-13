from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domains.inventory.enums import PonType
from app.domains.inventory.schemas.pon_port import PonPortCreate, PonPortUpdate


class TestPonPortCreate:
    def test_default_pon_type_is_gpon(self) -> None:
        payload = PonPortCreate(slot_id=uuid4(), pon_index=0)
        assert payload.pon_type == PonType.GPON

    def test_accepts_xg_pon(self) -> None:
        # XG-PON foi adicionado pela migration 0002 (rename de XGSPON).
        payload = PonPortCreate(
            slot_id=uuid4(),
            pon_index=0,
            pon_type=PonType.XG_PON,
        )
        assert payload.pon_type.value == "XG-PON"

    def test_accepts_xgs_pon(self) -> None:
        payload = PonPortCreate(
            slot_id=uuid4(),
            pon_index=0,
            pon_type=PonType.XGS_PON,
        )
        assert payload.pon_type.value == "XGS-PON"

    def test_rejects_negative_index(self) -> None:
        with pytest.raises(ValidationError):
            PonPortCreate(slot_id=uuid4(), pon_index=-1)

    def test_status_not_in_create(self) -> None:
        assert "status" not in PonPortCreate.model_fields


class TestPonPortUpdate:
    def test_slot_id_and_index_immutable(self) -> None:
        fields = set(PonPortUpdate.model_fields.keys())
        assert fields == {"pon_type", "status"}
