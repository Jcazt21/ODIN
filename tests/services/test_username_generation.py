"""Usuario derivado del nombre: inicial del nombre + 4 primeras del apellido.

La normalización no es cosmética: si un acento o una ñ entraran al `username`,
habría que teclearlos para entrar, y el login se volvería una trampa para
nombres perfectamente comunes acá.
"""
from __future__ import annotations

import pytest

from odin.services.user_service import username_from_name


class TestBasicRule:
    def test_first_letter_of_name_plus_four_of_surname(self):
        assert username_from_name("Yvan", "Mercado") == "ymerc"

    def test_lowercases(self):
        assert username_from_name("JUAN", "PEREZ") == "jpere"

    def test_a_short_surname_just_yields_a_shorter_username(self):
        assert username_from_name("Ana", "Paz") == "apaz"


class TestNormalization:
    @pytest.mark.parametrize(
        ("first", "last", "expected"),
        [
            ("Yván", "Núñez", "ynune"),
            ("Ángel", "Óleo", "aoleo"),
            ("José", "Güell", "jguel"),
        ],
    )
    def test_strips_accents_and_enye(self, first, last, expected):
        assert username_from_name(first, last) == expected

    def test_drops_spaces_in_a_compound_surname(self):
        """"De la Cruz" es UN apellido; se toman sus 4 primeras letras."""
        assert username_from_name("María", "De la Cruz") == "mdela"

    def test_drops_punctuation(self):
        assert username_from_name("Sean", "O'Brien") == "sobri"

    def test_uses_only_the_first_given_name(self):
        assert username_from_name("Ana María", "Reyes") == "areye"


class TestRejectsUnusableInput:
    @pytest.mark.parametrize(("first", "last"), [("", "Mercado"), ("Yvan", ""), ("", ""), ("123", "456")])
    def test_raises_when_there_is_nothing_to_build_from(self, first, last):
        with pytest.raises(ValueError):
            username_from_name(first, last)
