"""Guarda contra la regresión de empaquetado de la plantilla .docx.

Mismo riesgo que el catálogo geográfico (ver tests/db/test_seed_packaging.py):
setuptools instala solo módulos `.py` salvo que los datos se declaren en
`[tool.setuptools.package-data]`. Sin esa línea la exportación a Word funciona
en dev y en esta misma suite, y falla solo dentro del contenedor —que instala
el paquete— con un FileNotFoundError al pulsar "Exportar a Word".

Por eso se mira la configuración y no solo el archivo en disco.
"""
from __future__ import annotations

import tomllib
from pathlib import Path

from odin.services.export_service import _TEMPLATE

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = REPO_ROOT / "src" / "odin"


def test_the_template_exists():
    assert Path(str(_TEMPLATE)).is_file()


def test_the_template_lives_inside_the_installable_package():
    assert Path(str(_TEMPLATE)).is_relative_to(PACKAGE_ROOT)


def test_pyproject_declares_the_template_as_package_data():
    with (REPO_ROOT / "pyproject.toml").open("rb") as fh:
        pyproject = tomllib.load(fh)

    patterns = pyproject["tool"]["setuptools"]["package-data"]["odin"]
    relative = Path(str(_TEMPLATE)).relative_to(PACKAGE_ROOT)

    assert any(
        relative.match(pattern) for pattern in patterns
    ), f"ningún patrón de package-data ({patterns}) cubre {relative}"


def test_the_template_keeps_the_styles_the_export_writes():
    """Si alguien reemplaza la plantilla sin estos estilos, el export revienta
    al pedirlos por nombre. Mejor que falle acá."""
    from docx import Document

    with _TEMPLATE.open("rb") as handle:
        estilos = {s.name for s in Document(handle).styles}

    for requerido in [
        "ODIN Title",
        "ODIN Subtitle",
        "ODIN Kicker",
        "ODIN Report Title",
        "ODIN Meta",
        "ODIN Divider",
        "ODIN Body",
    ]:
        assert requerido in estilos, f"la plantilla no define {requerido!r}"
