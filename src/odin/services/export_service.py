"""Exportación de reportes a un documento de Word (.docx).

Se genera en memoria y se devuelve como bytes: los documentos son pequeños
(decenas de reportes) y así no hay archivos temporales que limpiar ni estado
compartido entre peticiones.
"""
from __future__ import annotations

import io
from datetime import date

from docx import Document
from docx.document import Document as DocxDocument
from docx.enum.text import WD_ALIGN_PARAGRAPH
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from odin.api import deps
from odin.db.models import Article
from odin.scrapers import source_name

# Etiquetas legibles para los códigos que guarda el análisis. El documento lo
# lee una persona, no un programa: "Negativo" dice más que "NEG".
_SENTIMENT_LABELS = {"POS": "Positivo", "NEG": "Negativo", "NEU": "Neutro"}


def _format_date(value: date | None) -> str:
    """Día/mes/año. Sin hora: es lo que pidió el cliente y lo que la columna
    `analyzed_on` guarda."""
    return value.strftime("%d/%m/%Y") if value else "—"


# `docx.Document` (importado arriba) es la función fábrica que crea el
# documento; la clase real, la que hace falta para anotar tipos, vive en
# `docx.document.Document` — de ahí el alias `DocxDocument`. Sin él mypy
# rechaza la anotación porque una función no es un tipo válido.
def _add_field(document: DocxDocument, label: str, value: str) -> None:
    paragraph = document.add_paragraph()
    run = paragraph.add_run(f"{label}: ")
    run.bold = True
    paragraph.add_run(value or "—")


def build_document(articles: list[Article]) -> bytes:
    """Arma el .docx con los reportes recibidos, en ese orden."""
    document = Document()

    heading = document.add_paragraph("Reportes de prensa")
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    heading.runs[0].bold = True
    heading.runs[0].font.size = None  # hereda el tamaño del estilo por defecto

    for index, article in enumerate(articles):
        if index:
            document.add_page_break()

        document.add_heading(article.title or "(sin título)", level=1)

        # El nombre y no el slug: el documento lo lee el cliente, no un programa.
        _add_field(document, "Medio", source_name(article.source))
        _add_field(document, "Sección", article.section or "—")
        _add_field(document, "Publicado", _format_date(
            article.published_at.date() if article.published_at else None
        ))
        _add_field(
            document,
            "Documentalista",
            article.documentalist.display_name if article.documentalist else "Automático",
        )
        _add_field(document, "Fecha de análisis", _format_date(article.analyzed_on))
        _add_field(document, "Tema", article.main_topic or "—")
        _add_field(
            document,
            "Sentimiento",
            _SENTIMENT_LABELS.get(article.overall_sentiment or "", "—"),
        )
        _add_field(document, "URL", article.url)

        if article.entities:
            _add_field(
                document,
                "Entidades",
                ", ".join(sorted({e.name for e in article.entities})),
            )

        if article.body:
            document.add_paragraph()
            document.add_paragraph(article.body)

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def export_articles(article_ids: list[int]) -> bytes:
    """Busca los reportes pedidos y devuelve el documento.

    Los ids que ya no existen se ignoran en vez de fallar: entre que el usuario
    vio la lista y pulsó exportar, alguien pudo borrar uno, y perder la descarga
    entera por eso sería peor que entregar el resto. Solo se devuelve 404 si no
    queda ninguno.
    """
    if not article_ids:
        raise HTTPException(status_code=422, detail="No hay reportes seleccionados.")

    session = deps.get_session()
    try:
        rows = session.scalars(
            select(Article)
            .options(selectinload(Article.entities), selectinload(Article.documentalist))
            .where(Article.id.in_(article_ids))
        ).all()
        if not rows:
            raise HTTPException(
                status_code=404, detail="Ninguno de los reportes seleccionados existe."
            )

        # Respetar el orden en que llegaron los ids: es el que el usuario ve en
        # pantalla, y `IN (...)` no garantiza ninguno.
        by_id = {row.id: row for row in rows}
        ordered = [by_id[i] for i in article_ids if i in by_id]
        return build_document(ordered)
    finally:
        session.close()
