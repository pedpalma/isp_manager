# Testes unitários do Actor.

import dataclasses

import pytest

from app.core.actor import Actor, system_actor


def test_system_actor_is_marked_as_system():
    a = system_actor()
    assert a.is_system is True
    assert a.username == "system"
    assert a.actor_id is None


def test_actor_is_frozen():
    # Garantia de que ninguém muta o ator depois de criado (passado adiante
    # nas chamadas dos services).
    a = system_actor()
    with pytest.raises(dataclasses.FrozenInstanceError):
        a.username = "outro"  # type: ignore[misc]
