from uuid import UUID

import pytest

from app.core.exceptions import ValidationError
from app.core.ids import is_valid_id, new_id, new_id_str, parse_id


def test_new_id_returns_uuid_and_is_unique():
    a, b = new_id(), new_id()
    assert isinstance(a, UUID)
    assert a != b


def test_new_id_str_is_parseable():
    assert isinstance(UUID(new_id_str()), UUID)


def test_parse_id_accepts_uuid_and_str():
    u = new_id()
    assert parse_id(u) is u
    assert parse_id(str(u)) == u


@pytest.mark.parametrize("bad", ["", "not-a-uuid", "123", None])
def test_parse_id_rejects_garbage(bad):
    with pytest.raises(ValidationError):
        parse_id(bad)


def test_is_valid_id():
    assert is_valid_id(new_id_str()) is True
    assert is_valid_id("nope") is False
