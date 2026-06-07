from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.core.exceptions import ValidationError
from app.core.time import ensure_utc, parse_iso, to_iso, utcnow


def test_utcnow_is_aware_utc():
    now = utcnow()
    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)


def test_ensure_utc_naive_is_assumed_utc():
    naive = datetime(2026, 1, 1, 12, 0, 0)
    out = ensure_utc(naive)
    assert out.tzinfo is not None
    assert out.hour == 12


def test_ensure_utc_converts_other_timezone():
    saopaulo = timezone(timedelta(hours=-3))
    dt = datetime(2026, 1, 1, 9, 0, 0, tzinfo=saopaulo)
    out = ensure_utc(dt)
    assert out.utcoffset() == timedelta(0)
    assert out.hour == 12


def test_to_iso_is_utc():
    assert to_iso(datetime(2026, 1, 1, tzinfo=UTC)).endswith("+00:00")


def test_parse_iso_roundtrip():
    original = utcnow().replace(microsecond=0)
    assert parse_iso(to_iso(original)) == original


@pytest.mark.parametrize("bad", ["", "ontem", "2026-13-99"])
def test_parse_iso_rejects_garbage(bad):
    with pytest.raises(ValidationError):
        parse_iso(bad)
