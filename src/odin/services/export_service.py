"""Exportación de reportes a un documento de Word (.docx).

Se genera en memoria y se devuelve como bytes: los documentos son pequeños
(decenas de reportes) y así no hay archivos temporales que limpiar ni estado
compartido entre peticiones.
"""
from __future__ import annotations

import io
from datetime import date
from importlib.resources import files

from docx import Document
from docx.document import Document as DocxDocument
from docx.shared import RGBColor
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from odin.analysis.text_norm import norm_key
from odin.api import deps
from odin.db.models import Article
from odin.scrapers import source_name

# Etiquetas legibles para los códigos que guarda el análisis. El documento lo
# lee una persona, no un programa: "Negativo" dice más que "NEG".
_SENTIMENT_LABELS = {"POS": "Positivo", "NEG": "Negativo", "NEU": "Neutro"}


# Un ladillo del medio ("Alegada negligencia", "POLÍTICA") es corto y no cierra
# en punto. El umbral es generoso a propósito: descartar prosa real por error es
# peor que dejar pasar un ladillo, porque el cliente no puede recuperar lo que
# no se exportó.
_KICKER_MAX_CHARS = 60


def _is_section_kicker(paragraph: str) -> bool:
    """¿Es un ladillo de sección y no un párrafo de la nota?

    Se exige que sea corto Y que no termine en puntuación de cierre: una frase
    breve pero terminada ("«El peso pudo más que el techo», afirmó.") es prosa
    y se conserva.
    """
    if len(paragraph) > _KICKER_MAX_CHARS:
        return False
    return not paragraph.rstrip().endswith((".", "?", "!", "…", '"', "”", "»"))


def clean_body(body: str | None, *, title: str, topic: str | None) -> list[str]:
    """Párrafos del cuerpo, sin lo que arrastra el scrape.

    Lo que viene del sitio trae, antes de la nota, el tema suelto y el titular
    repetido; a veces el sumario aparece dos veces; y en el medio quedan
    ladillos de sección. En pantalla se toleran, pero el .docx lo imprime y
    entrega el cliente, y ahí se leen como errores.

    Reglas, las del README de la plantilla:
      - fuera el tema si aparece como párrafo
      - fuera el titular repetido
      - de un párrafo repetido queda solo la ÚLTIMA aparición
      - fuera los ladillos de sección

    Se conserva la última y no la primera por el caso que la motiva: el sumario
    viene suelto ANTES de la nota y otra vez en su lugar narrativo. Quedándose
    con la primera, el cuerpo abre resumiendo lo que va a contar; con la última,
    arranca donde arranca la nota.

    La comparación es insensible a mayúsculas y acentos porque el mismo texto
    vuelve del scrape con otra caja más seguido de lo que parece.
    """
    if not body:
        return []

    descartar = {norm_key(t) for t in (title, topic) if t}

    candidatos = [
        (norm_key(p), p)
        for p in (raw.strip() for raw in body.split("\n"))
        if p and norm_key(p) not in descartar and not _is_section_kicker(p)
    ]

    # Recorrido inverso para quedarse con la ÚLTIMA aparición de cada repetido,
    # y luego se restaura el orden original.
    vistos: set[str] = set()
    salida: list[str] = []
    for key, paragraph in reversed(candidatos):
        if key in vistos:
            continue
        vistos.add(key)
        salida.append(paragraph)

    return list(reversed(salida))


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


#: Plantilla con los estilos, el encabezado, el pie con número de página y el
#: tamaño de hoja. Se usa como archivo BASE en vez de recrear todo eso en
#: código: así ajustar la tipografía es editar el .docx, no tocar Python.
#: Empaquetada vía `[tool.setuptools.package-data]` en pyproject.toml.
_TEMPLATE = files("odin.exports") / "reportes-odin-template.docx"


def _load_template() -> DocxDocument:
    """Abre la plantilla y le quita los dos reportes de ejemplo.

    Se borra el cuerpo pero NO la `sectPr` final, que es donde viven el tamaño
    de hoja, los márgenes y las referencias al encabezado y al pie: quitarla
    devolvería el documento a los valores por defecto de Word.
    """
    with _TEMPLATE.open("rb") as handle:
        document = Document(handle)

    body = document.element.body
    for child in list(body):
        if not child.tag.endswith("}sectPr"):
            body.remove(child)
    return document


def _add_meta(document: DocxDocument, label: str, value: str) -> None:
    """Un dato con su etiqueta en negrita, en el estilo de la plantilla."""
    paragraph = document.add_paragraph(style="ODIN Meta")
    etiqueta = paragraph.add_run(f"{label}: ")
    etiqueta.bold = True
    etiqueta.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
    paragraph.add_run(value or "—")


def _period(articles: list[Article]) -> str:
    """Rango de publicación de los reportes, para el subtítulo."""
    fechas = sorted(a.published_at.date() for a in articles if a.published_at)
    if not fechas:
        return ""
    if fechas[0] == fechas[-1]:
        return f"{_format_date(fechas[0])}  ·  "
    return f"{_format_date(fechas[0])} – {_format_date(fechas[-1])}  ·  "


def build_document(articles: list[Article]) -> bytes:
    """Arma el .docx con los reportes recibidos, en ese orden."""
    document = _load_template()

    document.add_paragraph("Reportes de prensa", style="ODIN Title")
    total = f"{len(articles)} {'reporte' if len(articles) == 1 else 'reportes'}"
    document.add_paragraph(
        f"Análisis de prensa dominicana  ·  {_period(articles)}{total}",
        style="ODIN Subtitle",
    )

    for index, article in enumerate(articles):
        if index:
            document.add_page_break()

        sentimiento = _SENTIMENT_LABELS.get(article.overall_sentiment or "", "—")
        document.add_paragraph(
            f"Reporte {index + 1:02d}  ·  Sentimiento: {sentimiento}", style="ODIN Kicker"
        )
        document.add_paragraph(article.title or "(sin título)", style="ODIN Report Title")

        # El nombre y no el slug: el documento lo lee el cliente, no un programa.
        _add_meta(document, "Medio", source_name(article.source))
        _add_meta(document, "Sección", article.section or "—")
        _add_meta(
            document,
            "Publicado",
            _format_date(article.published_at.date() if article.published_at else None),
        )
        _add_meta(document, "Tema", article.main_topic or "—")
        _add_meta(
            document,
            "Documentalista",
            article.documentalist.display_name if article.documentalist else "Automático",
        )
        _add_meta(document, "Fecha de análisis", _format_date(article.analyzed_on))
        # Punto y coma y no coma: hay entidades que llevan coma adentro
        # ("Corporación del Acueducto y Alcantarillado, Santiago").
        _add_meta(
            document,
            "Entidades",
            "; ".join(sorted({e.name for e in article.entities})) if article.entities else "—",
        )
        _add_meta(document, "URL", article.url)

        document.add_paragraph(style="ODIN Divider")

        for paragraph in clean_body(
            article.body, title=article.title or "", topic=article.main_topic
        ):
            document.add_paragraph(paragraph, style="ODIN Body")

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
