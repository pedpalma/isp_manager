from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domains.inventory.schemas.vlan import VlanCreate, VlanUpdate


class TestVlanCreate:
    def test_minimal_valid(self) -> None:
        v = VlanCreate(olt_id=uuid4(), vlan_number=100)
        assert v.vlan_number == 100
        assert v.active is True
        assert v.name is None
        assert v.type is None

    def test_vlan_number_lower_bound_rejected(self) -> None:
        with pytest.raises(ValidationError):
            VlanCreate(olt_id=uuid4(), vlan_number=0)

    def test_vlan_number_upper_bound_rejected(self) -> None:
        with pytest.raises(ValidationError):
            VlanCreate(olt_id=uuid4(), vlan_number=4095)

    def test_vlan_number_edges_ok(self) -> None:
        assert VlanCreate(olt_id=uuid4(), vlan_number=1).vlan_number == 1
        assert VlanCreate(olt_id=uuid4(), vlan_number=4094).vlan_number == 4094

    def test_full_fields(self) -> None:
        v = VlanCreate(
            olt_id=uuid4(),
            vlan_number=200,
            name="dados",
            type="data",
            description="vlan de dados",
            active=False,
        )
        assert v.type == "data"
        assert v.active is False


class TestVlanUpdate:
    def test_immutable_fields_absent(self) -> None:
        fields = set(VlanUpdate.model_fields.keys())
        assert "olt_id" not in fields
        assert "vlan_number" not in fields
        assert {"name", "type", "description", "active"} <= fields

    def test_partial_update(self) -> None:
        u = VlanUpdate(active=False)
        assert u.model_dump(exclude_unset=True) == {"active": False}
