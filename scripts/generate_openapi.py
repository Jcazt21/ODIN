"""Vuelca el schema OpenAPI real de la API a un archivo JSON (tarea 25 de
task.md, §9.2).

`frontend/package.json` ("generate:types") corre `openapi-typescript` sobre
el resultado para producir `frontend/src/lib/api-types.ts`: los tipos TS del
frontend salen de las rutas y `response_model=` de `api.py`/`auth.py`, en vez
de mantenerse a mano en un tercer lugar.

Importar `api` carga el motor de análisis (`ODIN_ANALYZER`, por defecto
"local": spaCy + pysentimiento, sin costo — ver config.py y CLAUDE.md). Nunca
usa `ODIN_ANALYZER=gemini` para esto: no hace ninguna llamada, pero cargar
`GeminiAnalyzer` exige `google-genai` y no aporta nada al schema.

Uso:
    python scripts/generate_openapi.py                      # frontend/openapi.json
    python scripts/generate_openapi.py ruta/al/archivo.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from odin.core.config import settings  # noqa: E402

if settings.analyzer != "local":
    print(
        "ODIN_ANALYZER debe ser 'local' para generar el schema "
        f"(actual: {settings.analyzer!r}) — evita cargar el motor de pago solo "
        "para volcar tipos.",
        file=sys.stderr,
    )
    sys.exit(1)

from odin.api import app  # noqa: E402


def main() -> None:
    out = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else Path(__file__).resolve().parent.parent / "frontend" / "openapi.json"
    )
    out.write_text(json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"OpenAPI schema escrito en {out}")


if __name__ == "__main__":
    main()
