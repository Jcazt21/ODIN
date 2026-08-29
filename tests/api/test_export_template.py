"""El .docx exportado sigue la plantilla de docs/export 4.

Se usa el .docx como archivo base en vez de recrear los estilos en código: así
el encabezado, el pie con número de página, el tamaño de hoja y las nueve
definiciones de estilo vienen heredados, y ajustar la tipografía es editar la
plantilla y no tocar Python.
"""
from __future__ import annotations

import io
from datetime import UTC, date, datetime

import pytest
from docx import Document

from odin.core import auth
from odin.core.auth import create_token
from odin.db.models import Article, User


def _headers():
    token, _ = create_token("jperez")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def reports(sqlite_sessionmaker):
    session = sqlite_sessionmaker()
    session.add(
        User(
            username="jperez",
            display_name="Juan Pérez",
            first_name="Juan",
            last_name="Pérez",
            password_hash=auth.hash_password("x", iterations=1000),
            role="documentalista",
        )
    )
    session.commit()
    autor = session.query(User).filter_by(username="jperez").one().id

    ids = []
    for n, sentiment in ((1, "NEG"), (2, "POS")):
        article = Article(
            source="listin_diario",
            url=f"https://listindiario.com/n{n}",
            title=f"Titular del reporte {n}",
            section="Provincias",
            body=(
                f"tema suelto {n}\n"
                f"Titular del reporte {n}\n"
                "Primer párrafo real de la nota, con su punto final.\n"
                "Alegada negligencia\n"
                "Segundo párrafo real de la nota, también terminado."
            ),
            main_topic=f"tema suelto {n}",
            overall_sentiment=sentiment,
            published_at=datetime(2026, 8, n + 20, tzinfo=UTC),
            documentalist_id=autor,
            analyzed_on=date(2026, 8, 28),
        )
        session.add(article)
        session.commit()
        ids.append(article.id)
    session.close()
    return ids


def _doc(resp) -> Document:
    return Document(io.BytesIO(resp.content))


def _export(api_client, ids):
    resp = api_client.post("/api/articles/export", json={"article_ids": ids}, headers=_headers())
    assert resp.status_code == 200, resp.text
    return _doc(resp)


def _styles(doc) -> list[str]:
    return [p.style.name for p in doc.paragraphs]


class TestTemplateStyles:
    def test_uses_the_template_paragraph_styles(self, api_client, reports):
        doc = _export(api_client, reports)

        for style in ["ODIN Title", "ODIN Kicker", "ODIN Report Title", "ODIN Meta", "ODIN Body"]:
            assert style in _styles(doc), f"falta {style}"

    def test_keeps_the_running_header_and_page_number(self, api_client, reports):
        doc = _export(api_client, reports)
        section = doc.sections[0]

        assert "ODIN" in " ".join(p.text for p in section.header.paragraphs)
        assert "PAGE" in section.footer.paragraphs[0]._p.xml

    def test_keeps_letter_size_and_one_inch_margins(self, api_client, reports):
        doc = _export(api_client, reports)
        section = doc.sections[0]

        assert section.page_width == 7772400  # Letter
        assert section.left_margin == 914400  # 1"

    def test_carries_no_leftovers_from_the_template_examples(self, api_client, reports):
        """La plantilla trae dos reportes de muestra que no deben viajar."""
        doc = _export(api_client, reports)
        text = "\n".join(p.text for p in doc.paragraphs)

        assert "Las Charcas" not in text
        assert "PLD:" not in text


class TestStructure:
    def test_opens_with_the_document_title_and_a_subtitle(self, api_client, reports):
        doc = _export(api_client, reports)

        assert doc.paragraphs[0].text == "Reportes de prensa"
        assert doc.paragraphs[0].style.name == "ODIN Title"
        assert doc.paragraphs[1].style.name == "ODIN Subtitle"
        assert "2 reportes" in doc.paragraphs[1].text

    def test_numbers_each_report_and_states_its_sentiment(self, api_client, reports):
        doc = _export(api_client, reports)
        kickers = [p.text for p in doc.paragraphs if p.style.name == "ODIN Kicker"]

        assert kickers == [
            "Reporte 01  ·  Sentimiento: Negativo",
            "Reporte 02  ·  Sentimiento: Positivo",
        ]

    def test_metadata_follows_the_template_order(self, api_client, reports):
        doc = _export(api_client, reports)
        metas = [p.text.split(":")[0] for p in doc.paragraphs if p.style.name == "ODIN Meta"]

        assert metas[:8] == [
            "Medio",
            "Sección",
            "Publicado",
            "Tema",
            "Documentalista",
            "Fecha de análisis",
            "Entidades",
            "URL",
        ]

    def test_the_label_of_each_metadata_is_bold(self, api_client, reports):
        doc = _export(api_client, reports)
        meta = next(p for p in doc.paragraphs if p.style.name == "ODIN Meta")

        assert meta.runs[0].bold is True
        assert meta.runs[1].bold is not True


class TestBodyIsClean:
    def test_drops_the_topic_and_the_repeated_headline(self, api_client, reports):
        doc = _export(api_client, reports)
        body = [p.text for p in doc.paragraphs if p.style.name == "ODIN Body"]

        assert "tema suelto 1" not in body
        assert "Titular del reporte 1" not in body

    def test_drops_the_section_kicker(self, api_client, reports):
        doc = _export(api_client, reports)
        body = [p.text for p in doc.paragraphs if p.style.name == "ODIN Body"]

        assert "Alegada negligencia" not in body

    def test_keeps_the_real_paragraphs(self, api_client, reports):
        doc = _export(api_client, reports)
        body = [p.text for p in doc.paragraphs if p.style.name == "ODIN Body"]

        assert "Primer párrafo real de la nota, con su punto final." in body
        assert "Segundo párrafo real de la nota, también terminado." in body
