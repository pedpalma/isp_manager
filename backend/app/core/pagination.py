# Paginação reutilizável.
# Padrão simples offset/limit, suficiente para listas curtas de catálogo.
from __future__ import annotations

from typing import Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field, computed_field

T = TypeVar("T")


class PageParams(BaseModel):
    """Parâmetros de paginação lidos da query string da requisição."""

    page: int = Field(default=1, ge=1, description="Página começa em 1.")
    page_size: int = Field(default=50, ge=1, le=200, description="Itens por página (máximo 200)")

    @property
    def offset(self) -> int:
        # OFFSET do SQL: quantos registros pular antes de começar a ler.
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        # LIMIT do SQL: quantos registros trazer.
        return self.page_size


def page_params(
    page: int = Query(default=1, ge=1, description="Página começa em 1."),
    page_size: int = Query(default=50, ge=1, le=200, description="Itens por página (máximo 200)"),
) -> PageParams:
    """Dependency: lê `?page=...&page_size=...` da URL e devolve `PageParams`"""
    return PageParams(page=page, page_size=page_size)


class Page(BaseModel, Generic[T]):  # noqa: UP046
    """Página de resultados retornada pelas rotas de listagem."""

    # Permite que o response_model=Page[XxxRead] funcione com instâncias
    # ORM dentro de `items` (via ManufacturerRead.model_validate(orm_obj)).

    model_config = ConfigDict(from_attributes=True)

    items: list[T] = Field(description="Itens desta página.")
    total: int = Field(ge=0, description="Total de itens (todas as páginas).")
    page: int = Field(ge=1, description="Página atual (1-based).")
    page_size: int = Field(ge=1, description="Itens por página.")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_next(self) -> bool:
        return self.page * self.page_size < self.total

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_prev(self) -> bool:
        return self.page > 1
