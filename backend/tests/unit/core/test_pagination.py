# Testes unitários do módulo de paginação.
# Não tocam banco.

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.core.pagination import Page, PageParams


# ----- PageParams -----

def test_page_params_offset_first_page():
    p = PageParams(page=1, page_size=50)
    assert p.offset == 0
    assert p.limit == 50


def test_page_params_offset_third_page():
    p = PageParams(page=3, page_size=20)
    # 2 páginas inteiras puladas antes (40 itens).
    assert p.offset == 40
    assert p.limit == 20


def test_page_params_defaults():
    p = PageParams()
    assert p.page == 1
    assert p.page_size == 50


def test_page_params_rejects_page_zero():
    with pytest.raises(PydanticValidationError):
        PageParams(page=0)


def test_page_params_rejects_page_negative():
    with pytest.raises(PydanticValidationError):
        PageParams(page=-1)


def test_page_params_rejects_page_size_too_large():
    with pytest.raises(PydanticValidationError):
        PageParams(page=1, page_size=201)


def test_page_params_rejects_page_size_zero():
    with pytest.raises(PydanticValidationError):
        PageParams(page=1, page_size=0)


# ----- Page (has_next / has_prev) -----

def test_page_has_next_when_more_pages_remain():
    # 50 itens por página, total 200 -> ainda há pelo menos uma página depois.
    p = Page[int](items=list(range(50)), total=200, page=1, page_size=50)
    assert p.has_next is True
    assert p.has_prev is False


def test_page_has_next_false_on_last_page():
    # Página 4 de 4 (50 * 4 = 200, igual ao total).
    p = Page[int](items=list(range(50)), total=200, page=4, page_size=50)
    assert p.has_next is False
    assert p.has_prev is True


def test_page_has_next_false_when_total_smaller_than_page():
    # Total 30, página 1 com tamanho 50: cabe tudo na primeira página.
    p = Page[int](items=list(range(30)), total=30, page=1, page_size=50)
    assert p.has_next is False
    assert p.has_prev is False


def test_page_computed_fields_appear_in_json():
    p = Page[int](items=[1, 2, 3], total=3, page=1, page_size=50)
    dumped = p.model_dump()
    assert dumped["has_next"] is False
    assert dumped["has_prev"] is False
    assert dumped["items"] == [1, 2, 3]
    assert dumped["total"] == 3
