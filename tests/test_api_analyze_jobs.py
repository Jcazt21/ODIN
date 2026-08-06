"""Pruebas de POST /api/analyze → 202 + job_id y GET /api/jobs/{id} (§3.1 de
task.md, tarea 15): antes el endpoint hacía descarga+NLP síncronamente dentro
del request (hasta ~60s); ahora encola un `AnalyzeJob` y el trabajo corre en
`BackgroundTasks`.

`TestClient` ejecuta las `BackgroundTasks` de forma síncrona al final del
request (sin loop de eventos real de por medio), así que no hace falta
sleep/polling en los tests: para cuando `api_client.post(...)` retorna, el job
ya corrió y quedó en su estado final. Sin red, sin spaCy/pysentimiento/Gemini:
`_fetch_and_extract` y `_analyzer.analyze` se reemplazan con dobles.
"""
from __future__ import annotations

from analysis.base import AnalysisResult
from auth import create_token
from db.models import AnalyzeJob, Article
from services import analyze_service


def _auth_headers() -> dict[str, str]:
    token, _ = create_token("tester")
    return {"Authorization": f"Bearer {token}"}


def _fake_analysis_result() -> AnalysisResult:
    """Doble del análisis, construido con el `AnalysisResult` REAL.

    Antes era una clase aparte que redeclaraba a mano cada atributo; cada campo
    nuevo del análisis había que acordarse de copiarlo aquí, y si no, el job
    fallaba con AttributeError en un test que no tenía nada que ver con ese
    campo. Usando el dataclass real, los campos nuevos llegan con su valor por
    defecto y el doble no puede volver a quedarse atrás."""
    return AnalysisResult(main_topic="elecciones", overall_sentiment="NEU", sentiment_score=0.5)


class TestAnalyzeAlreadySaved:
    def test_existing_url_returns_200_directly_no_job(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        session.add(
            Article(
                source="diario_libre",
                url="https://diariolibre.com/ya-existe",
                title="Título",
                body="cuerpo",
            )
        )
        session.commit()
        session.close()

        resp = api_client.post(
            "/api/analyze", json={"url": "https://diariolibre.com/ya-existe"}, headers=_auth_headers()
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["already_saved"] is True
        # No debe haberse creado ningún job para una URL ya guardada.
        session = sqlite_sessionmaker()
        assert session.query(AnalyzeJob).count() == 0
        session.close()


class TestAnalyzeNewUrlEnqueuesJob:
    def _patch_pipeline(self, monkeypatch):
        import url_guard

        monkeypatch.setattr(url_guard, "validate_url", lambda url: url)
        monkeypatch.setattr(
            analyze_service,
            "fetch_and_extract",
            lambda url: {
                "title": "Título extraído",
                "body": "cuerpo extraído",
                "authors": None,
                "section": None,
                "published_at": None,
                "sitename": "diario_libre",
            },
        )
        monkeypatch.setattr(analyze_service, "analyze_safely", lambda title, body: _fake_analysis_result())
        monkeypatch.setattr(analyze_service, "arbitrate_ambiguous_persons", lambda result: None)
        monkeypatch.setattr(analyze_service, "canonicalize_result", lambda result: None)

    def test_returns_202_with_job_id(self, monkeypatch, api_client, sqlite_sessionmaker):
        self._patch_pipeline(monkeypatch)

        resp = api_client.post(
            "/api/analyze", json={"url": "https://diariolibre.com/nueva"}, headers=_auth_headers()
        )
        assert resp.status_code == 202
        body = resp.json()
        assert "job_id" in body
        assert body["status"] == "pending"

    def test_job_completes_and_result_is_available(self, monkeypatch, api_client, sqlite_sessionmaker):
        self._patch_pipeline(monkeypatch)

        resp = api_client.post(
            "/api/analyze", json={"url": "https://diariolibre.com/nueva-2"}, headers=_auth_headers()
        )
        job_id = resp.json()["job_id"]

        job_resp = api_client.get(f"/api/jobs/{job_id}", headers=_auth_headers())
        assert job_resp.status_code == 200
        job_body = job_resp.json()
        assert job_body["status"] == "done"
        assert job_body["error"] is None
        assert job_body["result"]["title"] == "Título extraído"
        assert job_body["result"]["already_saved"] is False
        assert job_body["result"]["main_topic"] == "elecciones"

    def test_job_failure_is_reported_not_raised(self, monkeypatch, api_client, sqlite_sessionmaker):
        import url_guard

        monkeypatch.setattr(url_guard, "validate_url", lambda url: url)

        def _boom(url):
            raise RuntimeError("la extracción falló")

        monkeypatch.setattr(analyze_service, "fetch_and_extract", _boom)

        resp = api_client.post(
            "/api/analyze", json={"url": "https://diariolibre.com/falla"}, headers=_auth_headers()
        )
        job_id = resp.json()["job_id"]

        job_resp = api_client.get(f"/api/jobs/{job_id}", headers=_auth_headers())
        job_body = job_resp.json()
        assert job_body["status"] == "failed"
        assert "la extracción falló" in job_body["error"]
        assert job_body["result"] is None

    def test_invalid_url_never_creates_a_job(self, monkeypatch, api_client, sqlite_sessionmaker):
        import url_guard
        from url_guard import UrlNotAllowed

        def _reject(url):
            raise UrlNotAllowed("dominio no permitido")

        monkeypatch.setattr(url_guard, "validate_url", _reject)

        resp = api_client.post(
            "/api/analyze", json={"url": "https://noallowed.example.com/x"}, headers=_auth_headers()
        )
        assert resp.status_code == 400
        session = sqlite_sessionmaker()
        assert session.query(AnalyzeJob).count() == 0
        session.close()


class TestGetJob:
    def test_unknown_job_returns_404(self, api_client):
        resp = api_client.get("/api/jobs/does-not-exist", headers=_auth_headers())
        assert resp.status_code == 404

    def test_requires_auth(self, api_client):
        resp = api_client.get("/api/jobs/anything")
        assert resp.status_code == 401
