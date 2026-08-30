"""El lock tiene que cubrir todo lo declarado en requirements.txt.

`Dockerfile.backend` instala desde `requirements.lock` con `--require-hashes` y
después hace `pip install --no-deps .`, así que una dependencia que esté en
requirements.txt pero no en el lock NO llega a la imagen. El síntoma no aparece
en los tests —el entorno local sí la tiene— sino al arrancar el contenedor, con
un ModuleNotFoundError al importar. Fue exactamente lo que pasó con
python-docx.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _normalize(name: str) -> str:
    """PEP 503: los nombres de paquete no distinguen mayúsculas ni -/_/. entre sí."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _declared() -> set[str]:
    names = set()
    for raw in (ROOT / "requirements.txt").read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        names.add(_normalize(re.split(r"[<>=!~\[;]", line)[0].strip()))
    return names


def _locked() -> set[str]:
    names = set()
    for raw in (ROOT / "requirements.lock").read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "--", "\\")):
            continue
        if "==" not in line:
            continue
        names.add(_normalize(line.split("==", 1)[0].strip()))
    return names


def test_every_declared_requirement_is_locked():
    missing = _declared() - _locked()

    assert not missing, (
        "Faltan en requirements.lock: "
        + ", ".join(sorted(missing))
        + ". Regeneralo con el comando del README (uv pip compile …); si no, "
        "la imagen de Docker arranca sin esos paquetes."
    )
