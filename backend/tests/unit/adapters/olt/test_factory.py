# Testes unitários da factory de OltAdapter.

from __future__ import annotations

import pytest

from app.adapters.olt.factory import get_olt_adapter
from app.adapters.olt.mock import MockOltAdapter
from app.core.exceptions import ConfigurationError


class TestSlugNone:
    """Sem slug -> default de settings. Em dev/testes, default é 'mock'."""

    def test_none_returns_mock_in_test_env(self) -> None:
        adapter = get_olt_adapter()
        assert isinstance(adapter, MockOltAdapter)

    def test_none_explicit_returns_mock(self) -> None:
        adapter = get_olt_adapter(manufacturer_slug=None)
        assert isinstance(adapter, MockOltAdapter)

    def test_empty_string_falls_back_to_default(self) -> None:
        # String vazia -> tratada como sem slug -> default.
        adapter = get_olt_adapter(manufacturer_slug="")
        assert isinstance(adapter, MockOltAdapter)

    def test_whitespace_only_falls_back_to_default(self) -> None:
        # Só espaços -> não bate KNOWN_SLUGS -> default.
        adapter = get_olt_adapter(manufacturer_slug="   ")
        assert isinstance(adapter, MockOltAdapter)


class TestSlugKnown:
    """Slugs mapeados. Fiberhome e ZTE são stubs (ConfigurationError)
    até o spike com lab real."""

    def test_fiberhome_raises_configuration_error(self) -> None:
        with pytest.raises(ConfigurationError) as exc:
            get_olt_adapter(manufacturer_slug="fiberhome")
        # Narrow para o type checker: ConfigurationError.details é
        # dict | None. Aqui sabemos que foi preenchido pela factory.
        assert exc.value.details is not None
        assert exc.value.details["olt_adapter"] == "fiberhome"

    def test_zte_raises_configuration_error(self) -> None:
        with pytest.raises(ConfigurationError) as exc:
            get_olt_adapter(manufacturer_slug="zte")
        assert exc.value.details is not None
        assert exc.value.details["olt_adapter"] == "zte"

    def test_case_normalization_uppercase(self) -> None:
        # "FIBERHOME" bate como known -> tenta instanciar -> stub error.
        with pytest.raises(ConfigurationError):
            get_olt_adapter(manufacturer_slug="FIBERHOME")

    def test_case_normalization_mixed(self) -> None:
        with pytest.raises(ConfigurationError):
            get_olt_adapter(manufacturer_slug="ZtE")

    def test_whitespace_around_known_slug_normalized(self) -> None:
        with pytest.raises(ConfigurationError):
            get_olt_adapter(manufacturer_slug="  fiberhome  ")


class TestSlugUnknown:
    """Slug não mapeado cai no default de settings, permitindo
    cadastrar novo fabricante sem quebrar coleta."""

    def test_unknown_slug_falls_back_to_default(self) -> None:
        adapter = get_olt_adapter(manufacturer_slug="huawei")
        assert isinstance(adapter, MockOltAdapter)

    def test_random_string_falls_back_to_default(self) -> None:
        adapter = get_olt_adapter(manufacturer_slug="nokia-brand-x")
        assert isinstance(adapter, MockOltAdapter)
