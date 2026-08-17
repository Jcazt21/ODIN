"""RuntimeSettings: fila única de preferencias configurables desde Ajustes
(hoy: el motor de análisis de POST /api/analyze), sin pasar por variables de
entorno ni reiniciar el proceso."""
from __future__ import annotations

from odin.db.models import RuntimeSettings


def test_persists_and_reads_back(db_session):
    db_session.add(RuntimeSettings(id=1, analyzer_mode="cascade"))
    db_session.commit()

    row = db_session.get(RuntimeSettings, 1)
    assert row.analyzer_mode == "cascade"
    assert row.updated_at is not None
