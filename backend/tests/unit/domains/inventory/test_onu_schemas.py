from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domains.inventory.enums import ConnectionStatus, SyncStatus
from app.domains.inventory.schemas.onu import (
    OnuCreate,
    OnuDetailRead,
    OnuRead,
    OnuRuntimeStateRead,
    OnuUpdate,
)


class TestOnuCreate:
    def test_minimal_valid(self) -> None:
        c = OnuCreate(
            onu_model_id=uuid4(),
            pon_port_id=uuid4(),
            serial="FHTT12345678",
        )
        assert c.onu_index is None
        assert c.description is None

    def test_serial_is_stripped_before_length_check(self) -> None:
        c = OnuCreate(onu_model_id=uuid4(), pon_port_id=uuid4(), serial="  ABCDEF  ")
        assert c.serial == "ABCDEF"

    def test_serial_too_short_after_strip_raises(self) -> None:
        # "  ab  " tem 6 chars com espaços, mas vira "ab" (2) após strip.
        with pytest.raises(ValidationError):
            OnuCreate(onu_model_id=uuid4(), pon_port_id=uuid4(), serial="  ab  ")

    def test_serial_empty_raises(self) -> None:
        with pytest.raises(ValidationError):
            OnuCreate(onu_model_id=uuid4(), pon_port_id=uuid4(), serial="    ")

    @pytest.mark.parametrize("bad_index", [-1, 1024, 99999])
    def test_onu_index_out_of_range_raises(self, bad_index: int) -> None:
        with pytest.raises(ValidationError):
            OnuCreate(
                onu_model_id=uuid4(),
                pon_port_id=uuid4(),
                serial="FHTT12345678",
                onu_index=bad_index,
            )

    def test_onu_index_and_description_accepted(self) -> None:
        c = OnuCreate(
            onu_model_id=uuid4(),
            pon_port_id=uuid4(),
            serial="FHTT12345678",
            onu_index=5,
            description="cliente joão / contrato 4821",
        )
        assert c.onu_index == 5
        assert c.description == "cliente joão / contrato 4821"


class TestOnuUpdate:
    def test_empty_update_is_noop(self) -> None:
        u = OnuUpdate()
        assert u.model_dump(exclude_unset=True) == {}

    def test_partial_only_description(self) -> None:
        u = OnuUpdate(description="nova nota")
        assert u.model_dump(exclude_unset=True) == {"description": "nova nota"}

    def test_explicit_null_clears_index(self) -> None:
        u = OnuUpdate(onu_index=None)
        assert u.model_dump(exclude_unset=True) == {"onu_index": None}

    def test_onu_index_out_of_range_raises(self) -> None:
        with pytest.raises(ValidationError):
            OnuUpdate(onu_index=5000)

    def test_immutable_fields_are_ignored(self) -> None:
        # serial / onu_model_id / pon_port_id não estão no schema de Update;
        # extra='ignore' (default) os descarta silenciosamente.
        u = OnuUpdate.model_validate(
            {"serial": "X", "onu_model_id": str(uuid4()), "description": "d"}
        )
        assert u.model_dump(exclude_unset=True) == {"description": "d"}


class TestOnuReadConstruction:
    def _onu_like(self) -> SimpleNamespace:
        return SimpleNamespace(
            onu_id=uuid4(),
            onu_model_id=uuid4(),
            pon_port_id=uuid4(),
            serial="FHTT12345678",
            onu_index=5,
            description=None,
            provisioned=False,
            line_profile_id=None,
            service_profile_id=None,
            provisioning_template_id=None,
            first_seen_at=None,
            last_seen_at=None,
            created_at=datetime.now(timezone.utc),  # noqa: UP017
            updated_at=datetime.now(timezone.utc),  # noqa: UP017
        )

    def _runtime_like(self) -> SimpleNamespace:
        return SimpleNamespace(
            connection_status="unknown",
            oper_state=None,
            sync_status="pending",
            last_signal_at=None,
            last_down_reason=None,
            distance_m=None,
            last_collected_at=None,
            updated_at=datetime.now(timezone.utc),  # noqa: UP017
        )

    def test_detail_with_runtime(self) -> None:
        base = OnuRead.model_validate(self._onu_like())
        runtime = OnuRuntimeStateRead.model_validate(self._runtime_like())
        detail = OnuDetailRead(**base.model_dump(), runtime=runtime)
        assert detail.runtime is not None
        assert detail.runtime.connection_status == ConnectionStatus.UNKNOWN
        assert detail.runtime.sync_status == SyncStatus.PENDING

    def test_detail_without_runtime(self) -> None:
        base = OnuRead.model_validate(self._onu_like())
        detail = OnuDetailRead(**base.model_dump())
        assert detail.runtime is None

    def test_read_has_no_runtime_field(self) -> None:
        # OnuRead (usado na listagem) não expõe runtime.
        assert "runtime" not in OnuRead.model_fields
        assert "runtime" in OnuDetailRead.model_fields
