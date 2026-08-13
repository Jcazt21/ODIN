"""Dependencias compartidas por los routers: sesión de BD y el analizador
activo (elegido por `ODIN_ANALYZER`, ver CLAUDE.md — nunca por la presencia
de una API key).

`get_session` se reexporta aquí (en vez de que cada router importe
`db.session.get_session` directo) para tener un único punto de import que
`tests/conftest.py` parchea con `monkeypatch.setattr(api.deps, "get_session",
...)` y que todos los routers heredan."""
from __future__ import annotations

from odin.core.observability import get_logger
from odin.db.session import get_session as get_session  # noqa: F401 (reexport)

log = get_logger("odin.api")
