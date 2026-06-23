# Testes unitários dos schemas Pydantic do domínio collection.

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domains.collection.enums import (
    JobStatus,
    JobTriggerType,
    PendingOnuState,
)
from app.domains.collection.schemas.collection_job import (
    CollectionJobCreate,
    CollectionJobDetailRead,
    CollectionJobRead,
)
from app.domains.collection.schemas.collection_log import CollectionLogRead
from app.domains.collection.schemas.pending_onu import PendingOnuRead


def test_collection_job_create_ok():
    payload = CollectionJobCreate(olt_id=uuid4())
    assert payload.olt_id is not None


def test_collection_job_create_missing_olt_id():
    with pytest.raises(ValidationError):
        CollectionJobCreate()  # type: ignore


def test_collection_job_read_round_trip():
    now = datetime.now(timezone.utc)  # noqa: UP017
    obj = CollectionJobRead(
        collection_job_id=uuid4(),
        olt_id=uuid4(),
        requested_by_user_id=uuid4(),
        job_type="discovery",
        trigger_type=JobTriggerType.MANUAL,
        target_scope=None,
        payload={},
        status=JobStatus.PENDING,
        retry_count=0,
        started_at=None,
        finished_at=None,
        error_message=None,
        created_at=now,
    )
    assert obj.status == JobStatus.PENDING


def test_collection_job_detail_carries_logs():
    now = datetime.now(timezone.utc)  # noqa: UP017
    base = {
        "collection_job_id": uuid4(),
        "olt_id": uuid4(),
        "requested_by_user_id": None,
        "job_type": "discovery",
        "trigger_type": JobTriggerType.MANUAL,
        "target_scope": None,
        "payload": None,
        "status": JobStatus.SUCCESS,
        "retry_count": 0,
        "started_at": now,
        "finished_at": now,
        "error_message": None,
        "created_at": now,
    }
    log = CollectionLogRead(
        collection_log_id=uuid4(),
        collection_job_id=base["collection_job_id"],
        olt_id=base["olt_id"],
        step_name="list_unprovisioned",
        command_sent="show gpon onu unconfigured",
        output_received="<mock>",
        parser_status="ok",
        success=True,
        duration_ms=1,
        executed_at=now,
    )
    detail = CollectionJobDetailRead(**base, logs=[log])
    assert len(detail.logs) == 1
    assert detail.logs[0].step_name == "list_unprovisioned"


def test_pending_onu_read_accepts_optional_fields():
    now = datetime.now(timezone.utc)  # noqa: UP017
    obj = PendingOnuRead(
        pending_onu_id=uuid4(),
        olt_id=uuid4(),
        pon_port_id=uuid4(),
        onu_model_id=None,
        linked_onu_id=None,
        serial="ABCD12345678",
        vendor_id=None,
        pon_position=None,
        state=PendingOnuState.DETECTED,
        is_duplicate=False,
        raw_payload=None,
        discovery_source="job:xyz",
        resolution_type=None,
        first_seen_at=now,
        last_seen_at=now,
        resolved_at=None,
        created_at=now,
        updated_at=now,
    )
    assert obj.state == PendingOnuState.DETECTED
    assert obj.is_duplicate is False
