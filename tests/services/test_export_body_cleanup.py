"""Limpieza del cuerpo scrapeado antes de exportarlo a Word.

Lo que llega del scrape trae, antes de la nota en sí, el tema suelto y el
titular repetido, a veces un sumario duplicado más abajo, y kickers de sección
en medio del texto ("Alegada negligencia"). En pantalla molestan poco; en un
documento que el cliente imprime y entrega, se leen como errores.

Las reglas son las del README de la plantilla (docs/EXPORT_DOCX.md).
"""
from __future__ import annotations

from odin.services.export_service import clean_body


class TestDropsTheHeadingsThatComeFromTheScrape:
    def test_drops_the_topic_when_it_opens_the_body(self):
        body = "crisis de agua potable\nBajo la consigna queremos agua, comunitarios..."

        assert clean_body(body, title="Las Charcas sin agua", topic="crisis de agua potable") == [
            "Bajo la consigna queremos agua, comunitarios..."
        ]

    def test_drops_the_headline_repeated_inside_the_text(self):
        body = "Las Charcas sin agua\nBajo la consigna queremos agua..."

        assert clean_body(body, title="Las Charcas sin agua", topic=None) == [
            "Bajo la consigna queremos agua..."
        ]

    def test_compares_ignoring_case_and_accents(self):
        """El scrape a veces devuelve el titular en otra caja."""
        body = "LAS CHARCAS SIN AGUA\nCuerpo real."

        assert clean_body(body, title="Las Charcás sin agua", topic=None) == ["Cuerpo real."]


class TestDropsRepeats:
    def test_keeps_the_last_copy_of_a_repeated_paragraph(self):
        """De un párrafo repetido se conserva la ÚLTIMA aparición.

        El caso real es el sumario: el scrape lo trae suelto ANTES de la nota y
        otra vez en su lugar narrativo. Conservando el primero, el cuerpo abría
        con un resumen de lo que venía después; conservando el último, arranca
        donde arranca la nota, como en la plantilla de referencia.
        """
        body = "Explican que Coraasan distribuyó agua.\nBajo la consigna...\nExplican que Coraasan distribuyó agua."

        assert clean_body(body, title="t", topic=None) == [
            "Bajo la consigna...",
            "Explican que Coraasan distribuyó agua.",
        ]


class TestDropsSectionKickers:
    def test_drops_a_short_titlecase_line_with_no_sentence(self):
        """"Alegada negligencia" es un ladillo del medio, no un párrafo."""
        body = "Primer párrafo con su punto final.\nAlegada negligencia\nSigue el texto de la nota."

        assert clean_body(body, title="t", topic=None) == [
            "Primer párrafo con su punto final.",
            "Sigue el texto de la nota.",
        ]

    def test_drops_an_all_caps_kicker(self):
        body = "POLÍTICA\nEl Congreso aprobó la ley este martes."

        assert clean_body(body, title="t", topic=None) == [
            "El Congreso aprobó la ley este martes."
        ]

    def test_keeps_a_short_paragraph_that_is_a_real_sentence(self):
        body = "Primer párrafo.\n“El peso pudo más que el techo”, afirmó."

        assert clean_body(body, title="t", topic=None) == [
            "Primer párrafo.",
            "“El peso pudo más que el techo”, afirmó.",
        ]


class TestTypography:
    """Lo que en pantalla pasa desapercibido y en papel se lee como descuido."""

    def test_straight_quotes_become_typographic(self):
        body = 'Bajo la consigna "queremos agua", los vecinos protestaron.'

        assert clean_body(body, title="t", topic=None) == [
            "Bajo la consigna “queremos agua”, los vecinos protestaron."
        ]

    def test_double_spaces_collapse(self):
        body = "Los comunitarios  se  concentraron frente a la oficina."

        assert clean_body(body, title="t", topic=None) == [
            "Los comunitarios se concentraron frente a la oficina."
        ]

    def test_a_non_breaking_space_is_a_space(self):
        """El scrape trae `&nbsp;` con más frecuencia de la que parece."""
        assert clean_body("Uno  dos.", title="t", topic=None) == ["Uno dos."]

    def test_an_unpaired_quote_does_not_flip_the_rest(self):
        """Se mira el carácter anterior, no se alterna a ciegas: una comilla
        suelta no puede dejar todas las siguientes al revés."""
        body = 'Dijo que "el peso pudo más. Y añadió: "no hay agua".'

        assert clean_body(body, title="t", topic=None) == [
            "Dijo que “el peso pudo más. Y añadió: “no hay agua”."
        ]


class TestEdges:
    def test_blank_lines_go_away(self):
        assert clean_body("Uno.\n\n\nDos.", title="t", topic=None) == ["Uno.", "Dos."]

    def test_an_empty_body_yields_nothing(self):
        assert clean_body("", title="t", topic=None) == []
        assert clean_body(None, title="t", topic=None) == []
