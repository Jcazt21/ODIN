"""requirements-ci.txt tiene que cubrir todo requirements.txt salvo lo pesado.

Los jobs "types" y "test" de .github/workflows/ci.yml no instalan el lock
completo: instalan requirements-ci.txt, que a propósito omite pysentimiento y
spacy (arrastran transformers/accelerate/torch, varios GB). Una dependencia
que se agregue a requirements.txt y no acá simplemente no existe en CI, y el
síntoma no aparece en local —el entorno de desarrollo sí la tiene— sino como
un ModuleNotFoundError al colectar los tests.

Fue exactamente lo que pasó con python-docx: 9 módulos de test rotos de una,
porque odin.api importa todos sus routers al cargarse, articles.py importa
export_service y export_service importa docx en el tope. Es el mismo modo de
falla que cubre test_requirements_lock.py, una capa más arriba.
"""
from __future__ import annotations

from tests.packaging.test_requirements_lock import _declared

#: Únicas omisiones intencionales. Ningún job de CI las ejercita: los tests que
#: usan spaCy se saltan solos con pytest.importorskip, y LocalAnalyzer importa
#: pysentimiento de forma perezosa.
_EXCLUIDAS = {"pysentimiento", "spacy"}


def test_every_light_requirement_is_in_the_ci_set():
    missing = _declared() - _declared("requirements-ci.txt") - _EXCLUIDAS

    assert not missing, (
        "Faltan en requirements-ci.txt: "
        + ", ".join(sorted(missing))
        + ". Los jobs 'types' y 'test' de CI corren sin esos paquetes; si algún "
        "import los necesita, CI falla aunque en local pase todo."
    )


def test_the_ci_set_has_no_leftovers():
    extra = _declared("requirements-ci.txt") - _declared()

    assert not extra, (
        "Sobran en requirements-ci.txt: "
        + ", ".join(sorted(extra))
        + ". Ya no están en requirements.txt: sacalas para que CI no instale "
        "algo que la aplicación no declara."
    )
