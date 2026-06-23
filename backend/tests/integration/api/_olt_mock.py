# Helpers de teste.

# Fornece:
# - set_canned_discovery / clear_canned_discovery: re-export dos helpers
# do MockOltAdapter para o teste injetar payload determinístico.

# - setup_inventory: monta cadeia FK completa via API
# (manufacturer -> olt_model -> credential -> olt -> chassis -> slot -> pon_port)
# e devolve dict com IDs.

# Por que helpers próprios em vez de importar de test_chassis.py:
# os testes de coleta precisam de slot + pon_port, além de OLT.

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

# Reexport dos helpers do MockOltAdapter para os testes não precisarem
# saber o caminho interno do modulo.
from app.adapters.olt.mock import (  # noqa: F401
    clear_canned_discovery,
    set_canned_discovery,
)

API = "/api/v1"


def _unique(prefix: str) -> str:
    return f"pytest-{prefix}-{uuid4().hex[:8]}"


def setup_inventory(real_client, headers: dict[str, str]) -> dict[str, Any]:
    """Cria cadeia completa de inventario via API e devolve IDs + indices.

    Devolve dict com chaves:
        manufacturer_id, olt_model_id, credential_id, olt_id,
        chassis_id, slot_id, pon_port_id, slot_index, pon_index.

    Indices fixos (slot=1, pon=1) para previsibilidade nos testes;
    múltiplas chamadas geram OLTs distintas (nome único)."""
    # 1 - manufacturer
    mfr_slug = _unique("mfr")
    r = real_client.post(
        f"{API}/manufacturers",
        headers=headers,
        json={"name": mfr_slug, "slug": mfr_slug, "active": True},
    )
    assert r.status_code == 201, r.text
    manufacturer_id = r.json()["manufacturer_id"]

    # 2 - olt_model
    olt_model_name = _unique("oltm")
    r = real_client.post(
        f"{API}/olt-models",
        headers=headers,
        json={
            "manufacturer_id": manufacturer_id,
            "model": olt_model_name,
            "active": True,
        },
    )
    assert r.status_code == 201, r.text
    olt_model_id = r.json()["olt_model_id"]

    # 3 - credential (secret_ref apontando para variável de ambiente
    # que o EnvSecretStore vai resolver durante a coleta)
    cred_label = _unique("cred")
    r = real_client.post(
        f"{API}/credentials",
        headers=headers,
        json={
            "label": cred_label,
            "username": "admin",
            "secret_ref": "PYTEST_OLT_SECRET",
            "auth_type": "password",
            "active": True,
        },
    )
    assert r.status_code == 201, r.text
    credential_id = r.json()["credential_id"]

    # 4 - olt
    olt_name = _unique("olt")
    # IP randomizado dentro de 10.0.0.0/8 para não conflitar com outros runs
    # (uq_olt_ip_port_active é parcial mas em testes seriais isso ainda importa).
    import secrets

    octets = [10, secrets.randbelow(256), secrets.randbelow(256), secrets.randbelow(254) + 1]
    olt_ip = ".".join(str(o) for o in octets)
    r = real_client.post(
        f"{API}/olts",
        headers=headers,
        json={
            "olt_model_id": olt_model_id,
            "credential_id": credential_id,
            "name": olt_name,
            "ip": olt_ip,
            "management_port": 22,
            "access_protocol": "SSH",
            "active": True,
        },
    )
    assert r.status_code == 201, r.text
    olt_id = r.json()["olt_id"]

    # 5) chassis
    r = real_client.post(
        f"{API}/chassis",
        headers=headers,
        json={"olt_id": olt_id, "chassis_index": 1},
    )
    assert r.status_code == 201, r.text
    chassis_id = r.json()["chassis_id"]

    # 6) slot
    slot_index = 1
    r = real_client.post(
        f"{API}/slots",
        headers=headers,
        json={
            "chassis_id": chassis_id,
            "slot_index": slot_index,
            "board_type": "GPBD",
        },
    )
    assert r.status_code == 201, r.text
    slot_id = r.json()["slot_id"]

    # 7) pon_port
    pon_index = 1
    r = real_client.post(
        f"{API}/pon-ports",
        headers=headers,
        json={
            "slot_id": slot_id,
            "pon_index": pon_index,
            "pon_type": "GPON",
        },
    )
    assert r.status_code == 201, r.text
    pon_port_id = r.json()["pon_port_id"]

    return {
        "manufacturer_id": UUID(manufacturer_id),
        "olt_model_id": UUID(olt_model_id),
        "credential_id": UUID(credential_id),
        "olt_id": UUID(olt_id),
        "chassis_id": UUID(chassis_id),
        "slot_id": UUID(slot_id),
        "pon_port_id": UUID(pon_port_id),
        "slot_index": slot_index,
        "pon_index": pon_index,
    }
