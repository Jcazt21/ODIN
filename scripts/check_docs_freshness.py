"""Checkpoint de documentación (task.md §10.1, tarea 30).

La documentación de Odin se desactualizó una vez en silencio (README describía
2 fuentes cuando había 8; `api.py` seguía citado meses después de partirse en
`api/` + `services/`) porque no había ningún punto en el flujo de cambios que
obligara a preguntarse "¿esto invalida algún doc?". Este script es ese punto:
corre en cada commit (`.pre-commit-config.yaml`) y avisa —sin bloquear— cuando
el commit toca una ruta que suele implicar un doc desactualizado y no toca
ningún doc.

No bloquea (`exit 0` siempre) a propósito: qué cuenta como "cambio que amerita
doc" es un juicio humano (un fix de un typo en `scrapers/base.py` no necesita
tocar ARQUITECTURA.md), y un gate duro sobre una heurística de rutas
produciría más falsos positivos ignorados que valor real. Es un recordatorio
en el punto exacto donde es más barato actuar, no una imposición.
"""
from __future__ import annotations

import subprocess
import sys

# (patrón de ruta que dispara el aviso, doc(s) a considerar, motivo corto)
_TRIGGERS: list[tuple[str, str, str]] = [
    ("db/models.py", "docs/DATA_DICTIONARY.md", "columna o tabla nueva"),
    ("api/schemas.py", "docs/ARQUITECTURA.md", "contrato de la API"),
    ("api/routers/", "docs/ARQUITECTURA.md", "endpoint nuevo o movido"),
    ("scrapers/", "README.md / docs/ARQUITECTURA.md / docs/PROCESOS.md", "fuente nueva o conteo de fuentes"),
    ("analysis/base.py", "docs/PROCESOS.md", "campo nuevo en AnalysisResult"),
    ("config.py", "docs/RUNBOOK.md", "variable de entorno nueva o cambiada"),
    ("alembic/versions/", "docs/DATA_DICTIONARY.md", "migración de esquema"),
]

_DOC_PATH_HINTS = ("docs/", "README.md")


def _staged_files() -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, check=False,
    )
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def main() -> int:
    files = _staged_files()
    if not files:
        return 0

    touched_docs = any(f.startswith(_DOC_PATH_HINTS) for f in files)
    if touched_docs:
        return 0  # ya se tocó algún doc en este commit: nada que avisar

    warnings = [
        f"  - tocaste {pattern!r} ({reason}) — ¿hace falta actualizar {doc}?"
        for pattern, doc, reason in _TRIGGERS
        if any(f.startswith(pattern) for f in files)
    ]
    if warnings:
        print("\n[checkpoint de documentación — no bloquea el commit]", file=sys.stderr)
        print("\n".join(warnings), file=sys.stderr)
        print(
            "Si el cambio no lo amerita, ignora esto. Detalle del checkpoint: "
            "README.md#checkpoint-de-documentación-1001-de-taskmd\n",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
