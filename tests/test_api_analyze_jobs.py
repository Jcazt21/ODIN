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

import dataclasses
from datetime import UTC, datetime, timedelta

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

    def test_expected_failure_shows_its_message(self, monkeypatch, api_client, sqlite_sessionmaker):
        """Los fallos previstos (`HTTPException`) llevan un texto pensado para
        el usuario: se muestra tal cual."""
        from fastapi import HTTPException

        import url_guard

        monkeypatch.setattr(url_guard, "validate_url", lambda url: url)

        def _boom(url):
            raise HTTPException(status_code=422, detail="No se pudo extraer el artículo de esa URL.")

        monkeypatch.setattr(analyze_service, "fetch_and_extract", _boom)

        resp = api_client.post(
            "/api/analyze", json={"url": "https://diariolibre.com/falla"}, headers=_auth_headers()
        )
        job_id = resp.json()["job_id"]

        job_body = api_client.get(f"/api/jobs/{job_id}", headers=_auth_headers()).json()
        assert job_body["status"] == "failed"
        assert job_body["error"] == "No se pudo extraer el artículo de esa URL."
        assert job_body["result"] is None

    def test_unexpected_failure_is_reported_without_leaking_internals(
        self, monkeypatch, api_client, sqlite_sessionmaker
    ):
        """Una excepción imprevista no debe salir cruda en el UI: el detalle va
        al log y el usuario recibe algo accionable. Lo que NO puede pasar es que
        se propague (nadie la atraparía: el job corre fuera del request)."""
        import url_guard

        monkeypatch.setattr(url_guard, "validate_url", lambda url: url)

        def _boom(url):
            raise RuntimeError("psycopg2.OperationalError: connection refused")

        monkeypatch.setattr(analyze_service, "fetch_and_extract", _boom)

        resp = api_client.post(
            "/api/analyze", json={"url": "https://diariolibre.com/falla-rara"}, headers=_auth_headers()
        )
        job_id = resp.json()["job_id"]

        job_body = api_client.get(f"/api/jobs/{job_id}", headers=_auth_headers()).json()
        assert job_body["status"] == "failed"
        assert "psycopg2" not in job_body["error"]
        assert "Intenta de nuevo" in job_body["error"]
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


class TestAnalyzeDoesNotRepeatWork:
    """Cada análisis evitado es una llamada al LLM que no se hace (y en modo
    `groq+gemini`, potencialmente una llamada facturada)."""

    def _count_analyses(self, monkeypatch) -> list[int]:
        """Parchea el pipeline contando cuántas veces se analiza de verdad."""
        import url_guard

        calls = [0]

        def _analyze(title, body):
            calls[0] += 1
            return _fake_analysis_result()

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
        monkeypatch.setattr(analyze_service, "analyze_safely", _analyze)
        monkeypatch.setattr(analyze_service, "arbitrate_ambiguous_persons", lambda result: None)
        monkeypatch.setattr(analyze_service, "canonicalize_result", lambda result: None)
        return calls

    def test_same_url_twice_is_analyzed_once(self, monkeypatch, api_client, sqlite_sessionmaker):
        calls = self._count_analyses(monkeypatch)
        url = "https://diariolibre.com/nota-repetida"

        first = api_client.post("/api/analyze", json={"url": url}, headers=_auth_headers())
        assert first.status_code == 202

        second = api_client.post("/api/analyze", json={"url": url}, headers=_auth_headers())
        # El segundo request ya trae el resultado, sin job ni análisis nuevo.
        assert second.status_code == 200
        assert second.json()["title"] == "Título extraído"
        assert calls[0] == 1

    def test_tracking_params_do_not_trigger_a_second_analysis(
        self, monkeypatch, api_client, sqlite_sessionmaker
    ):
        calls = self._count_analyses(monkeypatch)
        base = "https://diariolibre.com/nota-compartida"

        api_client.post("/api/analyze", json={"url": base}, headers=_auth_headers())
        resp = api_client.post(
            "/api/analyze",
            json={"url": f"{base}/?utm_source=whatsapp#top"},
            headers=_auth_headers(),
        )

        assert resp.status_code == 200
        assert calls[0] == 1

    def test_reuse_window_can_be_disabled(self, monkeypatch, api_client, sqlite_sessionmaker):
        calls = self._count_analyses(monkeypatch)
        monkeypatch.setattr(
            analyze_service,
            "settings",
            dataclasses.replace(analyze_service.settings, analyze_reuse_minutes=0),
        )
        url = "https://diariolibre.com/sin-reuso"

        api_client.post("/api/analyze", json={"url": url}, headers=_auth_headers())
        second = api_client.post("/api/analyze", json={"url": url}, headers=_auth_headers())

        assert second.status_code == 202
        assert calls[0] == 2

    def test_second_client_joins_the_job_already_running(
        self, monkeypatch, api_client, sqlite_sessionmaker
    ):
        # Un job `pending`/`running` de la misma URL: el segundo request debe
        # engancharse a ÉL en vez de lanzar un análisis en paralelo.
        import url_guard

        monkeypatch.setattr(url_guard, "validate_url", lambda url: url)
        url = "https://diariolibre.com/en-curso"
        session = sqlite_sessionmaker()
        session.add(AnalyzeJob(id="job-en-curso", url=url, status="running"))
        session.commit()
        session.close()

        resp = api_client.post("/api/analyze", json={"url": url}, headers=_auth_headers())

        assert resp.status_code == 202
        assert resp.json()["job_id"] == "job-en-curso"
        session = sqlite_sessionmaker()
        assert session.query(AnalyzeJob).count() == 1  # no se creó un segundo job
        session.close()

    def test_a_stale_running_job_is_not_joined(self, monkeypatch, api_client, sqlite_sessionmaker):
        # Un job colgado (proceso reiniciado a mitad) nunca va a terminar:
        # engancharse a él dejaría al cliente esperando para siempre.
        self._count_analyses(monkeypatch)
        url = "https://diariolibre.com/colgado"
        session = sqlite_sessionmaker()
        session.add(
            AnalyzeJob(
                id="job-colgado",
                url=url,
                status="running",
                created_at=datetime.now(UTC) - timedelta(hours=3),
            )
        )
        session.commit()
        session.close()

        resp = api_client.post("/api/analyze", json={"url": url}, headers=_auth_headers())

        assert resp.status_code == 202
        assert resp.json()["job_id"] != "job-colgado"


class TestReapStaleJobs:
    def test_interrupted_jobs_are_failed_with_a_readable_message(
        self, monkeypatch, api_client, sqlite_sessionmaker
    ):
        session = sqlite_sessionmaker()
        session.add_all([
            AnalyzeJob(
                id="viejo",
                url="https://diariolibre.com/a",
                status="running",
                created_at=datetime.now(UTC) - timedelta(hours=2),
            ),
            AnalyzeJob(
                id="reciente",
                url="https://diariolibre.com/b",
                status="running",
                created_at=datetime.now(UTC),
            ),
        ])
        session.commit()
        session.close()

        analyze_service.reap_stale_jobs()

        session = sqlite_sessionmaker()
        assert session.get(AnalyzeJob, "viejo").status == "failed"
        assert "interrumpió" in session.get(AnalyzeJob, "viejo").error
        assert session.get(AnalyzeJob, "reciente").status == "running"
        session.close()

    def test_finished_jobs_past_their_ttl_are_deleted(
        self, monkeypatch, api_client, sqlite_sessionmaker
    ):
        # `result_json` guarda el cuerpo completo del artículo: sin poda la
        # tabla crece sin techo.
        session = sqlite_sessionmaker()
        session.add_all([
            AnalyzeJob(
                id="antiguo",
                url="https://diariolibre.com/a",
                status="done",
                created_at=datetime.now(UTC) - timedelta(days=30),
            ),
            AnalyzeJob(
                id="de-ayer",
                url="https://diariolibre.com/b",
                status="done",
                created_at=datetime.now(UTC) - timedelta(hours=1),
            ),
        ])
        session.commit()
        session.close()

        analyze_service.reap_stale_jobs()

        session = sqlite_sessionmaker()
        assert session.get(AnalyzeJob, "antiguo") is None
        assert session.get(AnalyzeJob, "de-ayer") is not None
        session.close()


class TestGetJob:
    def test_unknown_job_returns_404(self, api_client):
        resp = api_client.get("/api/jobs/does-not-exist", headers=_auth_headers())
        assert resp.status_code == 404

    def test_requires_auth(self, api_client):
        resp = api_client.get("/api/jobs/anything")
        assert resp.status_code == 401

    def test_response_matches_the_declared_schema(self, api_client, sqlite_sessionmaker):
        """El handler arma el JSON a mano para no re-serializar el resultado en
        cada poll; esto vigila que lo que emite siga siendo un `JobResponse`."""
        from api.schemas import JobResponse

        session = sqlite_sessionmaker()
        session.add(
            AnalyzeJob(id="con-stage", url="https://diariolibre.com/x", status="running", stage="analyzing")
        )
        session.commit()
        session.close()

        body = api_client.get("/api/jobs/con-stage", headers=_auth_headers()).json()

        assert JobResponse.model_validate(body).stage == "analyzing"
        assert body == {
            "job_id": "con-stage",
            "status": "running",
            "stage": "analyzing",
            "error": None,
            "result": None,
        }
