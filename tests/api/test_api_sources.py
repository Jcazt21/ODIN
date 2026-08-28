"""Catálogo de medios para el formulario de captura manual.

Distinto de las facetas de /api/articles/filters, que solo listan medios con
reportes ya guardados: acá hacen falta todos los del registro, o el primer
reporte de un medio nunca se podría dar de alta.
"""
from __future__ import annotations

from odin.core.auth import create_token
from odin.scrapers import SCRAPERS


def _auth_headers():
    token, _ = create_token("tester")
    return {"Authorization": f"Bearer {token}"}


class TestSourceCatalog:
    def test_lists_every_registered_source(self, api_client):
        resp = api_client.get("/api/sources", headers=_auth_headers())

        assert resp.status_code == 200
        assert {s["value"] for s in resp.json()} == set(SCRAPERS)

    def test_pairs_each_slug_with_its_readable_name(self, api_client):
        resp = api_client.get("/api/sources", headers=_auth_headers())

        by_value = {s["value"]: s["label"] for s in resp.json()}
        assert by_value["listin_diario"] == "Listín Diario"
        assert by_value["el_dia"] == "El Día"

    def test_includes_sources_without_saved_reports(self, api_client):
        """La BD de la prueba está vacía y aun así vienen los 9: el catálogo
        sale del registro, no de lo guardado."""
        resp = api_client.get("/api/sources", headers=_auth_headers())

        assert len(resp.json()) == len(SCRAPERS)

    def test_sorted_by_label(self, api_client):
        labels = [s["label"] for s in api_client.get("/api/sources", headers=_auth_headers()).json()]

        assert labels == sorted(labels)

    def test_requires_authentication(self, api_client):
        assert api_client.get("/api/sources").status_code == 401
