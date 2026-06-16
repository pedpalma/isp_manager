from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domains.inventory.schemas.line_profile import (
    LineProfileCreate,
    LineProfileUpdate,
)


class TestLineProfileCreate:
    def test_minimal_valid(self) -> None:
        p = LineProfileCreate(
            olt_id=uuid4(),
            name="PLANO_600M",
            upstream_bandwidth="600M",
            downstream_bandwidth="600M",
        )
        assert p.version == "1"
        assert p.active is True
        assert p.raw_config is None
        assert p.logical_name is None

    def test_requires_both_bandwidths(self) -> None:
        with pytest.raises(ValidationError):
            LineProfileCreate(
                olt_id=uuid4(),
                name="x",
                upstream_bandwidth="1G",
            )  # type: ignore

    def test_raw_config_accepts_dict(self) -> None:
        p = LineProfileCreate(
            olt_id=uuid4(),
            name="x",
            upstream_bandwidth="1G",
            downstream_bandwidth="1G",
            raw_config={"tcont": 4, "gemport": 8},
        )
        assert p.raw_config is not None
        assert p.raw_config["tcont"] == 4

    def test_explicit_version(self) -> None:
        p = LineProfileCreate(
            olt_id=uuid4(),
            name="x",
            version="v2",
            upstream_bandwidth="1G",
            downstream_bandwidth="1G",
        )
        assert p.version == "v2"


class TestLineProfileUpdate:
    def test_immutable_fields_absent(self) -> None:
        fields = set(LineProfileUpdate.model_fields.keys())
        assert {"olt_id", "name", "version"} & fields == set()
        assert {
            "logical_name",
            "upstream_bandwidth",
            "downstream_bandwidth",
            "raw_config",
            "active",
        } <= fields

    def test_partial_bandwidth_update(self) -> None:
        u = LineProfileUpdate(upstream_bandwidth="2G")
        assert u.model_dump(exclude_unset=True) == {"upstream_bandwidth": "2G"}
