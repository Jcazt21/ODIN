"""Guarda contra la regresión de empaquetado del catálogo geográfico.

El JSON de la semilla vive junto al código, pero setuptools solo instala
módulos `.py` salvo que los datos se declaren en `[tool.setuptools.package-data]`.
Sin esa declaración todo funciona al correr desde el árbol de fuentes —dev y
esta misma suite— y falla solo dentro del contenedor, que instala el paquete:
la siembra muere con FileNotFoundError al arrancar, el selector de lugar queda
vacío y nada lo dice salvo los logs.

Por eso el test mira la configuración y no solo el archivo: comprobar que el
JSON existe en disco no habría detectado el bug.
"""
from __future__ import annotations

import tomllib
from pathlib import Path

import odin.db.localities as loc_store

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_seed_file_exists():
    assert loc_store.SEED_PATH.is_file()


def test_seed_file_lives_inside_the_installable_package():
    """Si el JSON se mueve fuera de `src/odin/`, ningún glob de package-data lo
    alcanza y vuelve a desaparecer al instalar."""
    assert loc_store.SEED_PATH.is_relative_to(REPO_ROOT / "src" / "odin")


def test_pyproject_declares_the_seed_as_package_data():
    with (REPO_ROOT / "pyproject.toml").open("rb") as fh:
        pyproject = tomllib.load(fh)

    patterns = pyproject["tool"]["setuptools"]["package-data"]["odin"]
    relative = loc_store.SEED_PATH.relative_to(REPO_ROOT / "src" / "odin")

    assert any(
        relative.match(pattern) for pattern in patterns
    ), f"ningún patrón de package-data ({patterns}) cubre {relative}"
