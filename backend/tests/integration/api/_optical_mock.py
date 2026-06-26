# Helpers de teste para signal_reading.
# Re-exporta set_canned_optical_readings / clear_canned_optical_readings
# do MockOltAdapter para os testes injetarem leituras determinísticas.
# Também oferece helpers de criação de ONU em uma cadeia já montada por
# setup_inventory (de _olt_mock.py).

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from app.adapters.olt.mock import (  # noqa: F401
    clear_canned_optical_readings,
    set_canned_optical_readings,
)

API = "/api/v1"


def _unique(prefix: str) -> str:
    return f"pytest-{prefix}-{uuid4().hex[:8]}"


def create_onu_for_pon(
    real_client,
    headers: dict[str, str],
    *,
    pon_port_id: UUID,
    onu_model_id: UUID,
    serial: str | None = None,
) -> dict[str, Any]:
    """Cria uma ONU viva na PON específica via API.
    Retorna o body do POST /onus."""
    if serial is None:
        serial = _unique("serial")[-12:].upper()
    r = real_client.post(
        f"{API}/onus",
        headers=headers,
        json={
            "onu_model_id": str(onu_model_id),
            "pon_port_id": str(pon_port_id),
            "serial": serial,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()
