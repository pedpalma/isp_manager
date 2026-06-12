# Testes unitários dos schemas da OLT.

# Não tocam banco. Validam só as regras declarativas do Pydantic e a
# imutabilidade de olt_model_id no Update.

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domains.inventory.enums import AccessProtocol, ConnectionStatus
from app.domains.inventory.schemas.olt import OltCreate, OltRead, OltUpdate


def _valid_create_payload() -> dict:
    return {
        "name": "pytest-olt-1",
        "ip": "10.0.0.10",
        "credential_id": str(uuid4()),
        "olt_model_id": str(uuid4()),
    }


# Defaults
def test_create_applies_defaults():
    olt = OltCreate(**_valid_create_payload())
    assert olt.management_port == 22
    assert olt.access_protocol is AccessProtocol.SSH
    assert olt.timezone == "UTC"
    assert olt.polling_enabled is True
    assert olt.active is True
    assert olt.hostname is None
    assert olt.firmware_version is None
    assert olt.location is None


# ip
def test_ip_accepts_host_ipv4():
    olt = OltCreate(**{**_valid_create_payload(), "ip": "192.168.1.1"})
    assert str(olt.ip) == "192.168.1.1"


def test_ip_accepts_host_ipv6():
    olt = OltCreate(**{**_valid_create_payload(), "ip": "2001:db8::1"})
    assert str(olt.ip) == "2001:db8::1"


def test_ip_rejects_cidr_mask():
    # IPvAnyAddress aceita só host. Rede/máscara deve falhar.
    with pytest.raises(ValidationError):
        OltCreate(**{**_valid_create_payload(), "ip": "10.0.0.0/24"})


def test_ip_rejects_garbage():
    with pytest.raises(ValidationError):
        OltCreate(**{**_valid_create_payload(), "ip": "not-an-ip"})


# management_port
@pytest.mark.parametrize("port", [1, 22, 161, 65535])
def test_port_accepts_valid_range(port):
    olt = OltCreate(**{**_valid_create_payload(), "management_port": port})
    assert olt.management_port == port


@pytest.mark.parametrize("port", [0, -1, 65536, 99999])
def test_port_rejects_out_of_range(port):
    with pytest.raises(ValidationError):
        OltCreate(**{**_valid_create_payload(), "management_port": port})


# timezone
@pytest.mark.parametrize("tz", ["UTC", "America/Sao_Paulo", "Europe/Lisbon"])
def test_timezone_accepts_iana(tz):
    olt = OltCreate(**{**_valid_create_payload(), "timezone": tz})
    assert olt.timezone == tz


@pytest.mark.parametrize("tz", ["Mars/Phobos", "GMT+3", "São Paulo", ""])
def test_timezone_rejects_non_iana(tz):
    with pytest.raises(ValidationError):
        OltCreate(**{**_valid_create_payload(), "timezone": tz})


# access_protocol
@pytest.mark.parametrize("proto", ["ssh", "telnet", "snmp"])
def test_access_protocol_accepts_enum_values(proto):
    olt = OltCreate(**{**_valid_create_payload(), "access_protocol": proto})
    assert olt.access_protocol.value == proto


def test_access_protocol_rejects_unknown():
    with pytest.raises(ValidationError):
        OltCreate(**{**_valid_create_payload(), "access_protocol": "http"})


# campos obrigatórios
def test_create_requires_credential_id():
    payload = _valid_create_payload()
    del payload["credential_id"]
    with pytest.raises(ValidationError):
        OltCreate(**payload)


def test_create_requires_olt_model_id():
    payload = _valid_create_payload()
    del payload["olt_model_id"]
    with pytest.raises(ValidationError):
        OltCreate(**payload)


def test_create_requires_ip():
    payload = _valid_create_payload()
    del payload["ip"]
    with pytest.raises(ValidationError):
        OltCreate(**payload)


def test_name_rejects_empty():
    with pytest.raises(ValidationError):
        OltCreate(**{**_valid_create_payload(), "name": ""})


# Update: imutabilidade de olt_model_id
def test_update_ignores_olt_model_id():
    # olt_model_id não é campo declarado no Update: o Pydantic ignora.
    # exclude_unset não deve conter olt_model_id mesmo se enviado.
    upd = OltUpdate(**{"name": "pytest-novo", "olt_model_id": str(uuid4())})
    dumped = upd.model_dump(exclude_unset=True)
    assert "olt_model_id" not in dumped
    assert dumped == {"name": "pytest-novo"}


def test_update_all_optional():
    # Update vazio é válido (nenhum campo obrigatório).
    upd = OltUpdate()
    assert upd.model_dump(exclude_unset=True) == {}


def test_update_validates_timezone_when_present():
    with pytest.raises(ValidationError):
        OltUpdate(timezone="Nowhere/Nope")


def test_update_allows_timezone_absent():
    upd = OltUpdate(name="pytest-x")
    assert "timezone" not in upd.model_dump(exclude_unset=True)


# Read: connection_status presente, deleted_at ausente
def test_read_has_connection_status_and_no_deleted_at():
    fields = set(OltRead.model_fields.keys())
    assert "connection_status" in fields
    assert "last_seen_at" in fields
    assert "last_collected_at" in fields
    assert "deleted_at" not in fields


def test_connection_status_enum_values():
    # Sanidade do enum: garante o conjunto esperado de estados.
    assert {s.value for s in ConnectionStatus} == {
        "unknown",
        "online",
        "offline",
        "degraded",
        "auth_failed",
        "timeout",
    }
