from __future__ import annotations

from uuid import uuid4

from app.domains.inventory.schemas.service_profile import (
    ServiceProfileCreate,
    ServiceProfileUpdate,
)


class TestServiceProfileCreate:
    def test_minimal_valid(self) -> None:
        p = ServiceProfileCreate(olt_id=uuid4(), name="SVC_INTERNET")
        assert p.version == "1"
        assert p.active is True
        assert p.raw_config is None

    def test_raw_config_accepts_dict(self) -> None:
        p = ServiceProfileCreate(olt_id=uuid4(), name="x", raw_config={"vlan": 100})
        assert p.raw_config is not None
        assert p.raw_config["vlan"] == 100

    def test_explicit_version(self) -> None:
        p = ServiceProfileCreate(olt_id=uuid4(), name="x", version="3")
        assert p.version == "3"


class TestServiceProfileUpdate:
    def test_immutable_fields_absent(self) -> None:
        fields = set(ServiceProfileUpdate.model_fields.keys())
        assert {"olt_id", "name", "version"} & fields == set()
        assert {"logical_name", "raw_config", "active"} <= fields

    def test_partial_update(self) -> None:
        u = ServiceProfileUpdate(logical_name="GLOBAL_SVC")
        assert u.model_dump(exclude_unset=True) == {"logical_name": "GLOBAL_SVC"}
