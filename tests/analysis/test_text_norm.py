import pytest

from odin.analysis.text_norm import slugify


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Política y Gobierno", "politica-y-gobierno"),
        ("  Salud   &  *Bienestar* ", "salud-bienestar"),
        ("***", ""),
        ("a-b", "a-b"),
    ],
)
def test_slugify(name, expected):
    assert slugify(name) == expected
