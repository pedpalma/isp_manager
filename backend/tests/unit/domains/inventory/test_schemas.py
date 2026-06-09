# Testes unitários dos schemas Pydantic do inventário.
# Não tocam banco: validam só regras do Pydantic (regex de slug, obrigatórios,
# semântica do PATCH com campos opcionais).

from uuid import uuid4

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.domains.inventory.schemas.manufacturer import (
    ManufacturerCreate,
    ManufacturerUpdate,
)
from app.domains.inventory.schemas.olt_model import OltModelCreate, OltModelUpdate
from app.domains.inventory.schemas.onu_model import OnuModelCreate


# ----- Manufacturer -----

def test_manufacturer_create_valid():
    m = ManufacturerCreate(name="Huawei", slug="huawei")
    assert m.name == "Huawei"
    assert m.slug == "huawei"
    assert m.active is True  # default


def test_manufacturer_create_rejects_uppercase_slug():
    with pytest.raises(PydanticValidationError):
        ManufacturerCreate(name="X", slug="Huawei")


def test_manufacturer_create_rejects_space_in_slug():
    with pytest.raises(PydanticValidationError):
        ManufacturerCreate(name="X", slug="huawei tech")


def test_manufacturer_create_rejects_slug_starting_with_dash():
    # Regex exige letra/dígito no primeiro caractere.
    with pytest.raises(PydanticValidationError):
        ManufacturerCreate(name="X", slug="-huawei")


def test_manufacturer_create_rejects_empty_name():
    with pytest.raises(PydanticValidationError):
        ManufacturerCreate(name="", slug="huawei")


def test_manufacturer_create_accepts_hyphen_and_underscore_in_slug():
    m = ManufacturerCreate(name="TP-Link", slug="tp-link")
    assert m.slug == "tp-link"
    m2 = ManufacturerCreate(name="V-SOL", slug="v_sol")
    assert m2.slug == "v_sol"


def test_manufacturer_update_all_fields_optional():
    # PATCH vazio é válido (sem mudanças). Service decide o que fazer.
    u = ManufacturerUpdate()
    assert u.model_dump(exclude_unset=True) == {}


def test_manufacturer_update_only_active():
    u = ManufacturerUpdate(active=False)
    assert u.model_dump(exclude_unset=True) == {"active": False}


# ----- OltModel -----

def test_olt_model_create_valid():
    mid = uuid4()
    m = OltModelCreate(manufacturer_id=mid, model="AN5516-04")
    assert m.manufacturer_id == mid
    assert m.model == "AN5516-04"
    assert m.active is True


def test_olt_model_update_has_no_manufacturer_id_field():
    # manufacturer_id é IMUTÁVEL: nem deve estar no schema de PATCH.
    assert "manufacturer_id" not in OltModelUpdate.model_fields


def test_olt_model_create_rejects_empty_model():
    with pytest.raises(PydanticValidationError):
        OltModelCreate(manufacturer_id=uuid4(), model="")


# ----- OnuModel -----

def test_onu_model_create_with_capabilities():
    m = OnuModelCreate(
        manufacturer_id=uuid4(),
        model="AN5506-04-F1",
        vendor_id="FHTT",
        category="residencial",
        capabilities_json={"wifi": True, "fxs": 2},
    )
    assert m.capabilities_json == {"wifi": True, "fxs": 2}


def test_onu_model_create_without_optionals():
    m = OnuModelCreate(manufacturer_id=uuid4(), model="F660")
    assert m.vendor_id is None
    assert m.category is None
    assert m.capabilities_json is None
    assert m.active is True
