"""Pruebas de la decodificación de HTML en url_guard.py (ruta de POST
/api/analyze: URLs que pega el usuario).

Regresión: este bug ya se había arreglado UNA VEZ en el crawler
(`scrapers/base.py`, con `apparent_encoding`) y volvió a aparecer por la otra
ruta, que decodificaba con `resp.encoding or "utf-8"`. Ese `or` no protege
nada: cuando el sitio no declara charset, `requests` rellena `resp.encoding`
con ISO-8859-1 (default del RFC 2616), que es un valor verdadero, así que el
fallback a UTF-8 nunca corría y los acentos llegaban mojibake ("versiÃ³n").

Sin red: se le pasa a `_decode_html` una respuesta de mentira con los headers
que interesan.
"""
from __future__ import annotations

from odin.core import url_guard

# Titular real de acento.com.do que destapó el bug, con tilde y comillas
# tipográficas (los dos casos que se rompían de forma distinta).
TITULAR = (
    "Danilo Medina rechaza versión de Abinader sobre deuda y "
    "acusa al Gobierno de repetir una «mentira»"
)


class _FakeResponse:
    """Lo único que `_decode_html` mira de la respuesta es el Content-Type."""

    def __init__(self, content_type: str) -> None:
        self.headers = {"Content-Type": content_type}


class TestDecodeHtml:
    def test_utf8_without_charset_header_is_not_mangled(self):
        # El caso de acento.com.do: cuerpo UTF-8, header sin charset.
        html = url_guard._decode_html(TITULAR.encode("utf-8"), _FakeResponse("text/html"))
        assert html == TITULAR
        assert "Ã" not in html  # firma del mojibake

    def test_utf8_with_declared_charset(self):
        html = url_guard._decode_html(
            TITULAR.encode("utf-8"), _FakeResponse("text/html; charset=utf-8")
        )
        assert html == TITULAR

    def test_declared_latin1_is_respected(self):
        # Un sitio que SÍ es latin-1 y lo declara debe seguir leyéndose bien:
        # el arreglo no puede ser "asumir UTF-8 siempre".
        html = url_guard._decode_html(
            TITULAR.encode("latin-1"), _FakeResponse("text/html; charset=ISO-8859-1")
        )
        assert html == TITULAR

    def test_unknown_charset_falls_back_to_detection(self):
        # Charset mal escrito/inventado por el sitio: no debe reventar con
        # LookupError, se detecta por contenido.
        html = url_guard._decode_html(
            TITULAR.encode("utf-8"), _FakeResponse("text/html; charset=utf8mb4")
        )
        assert html == TITULAR

    def test_undecodable_bytes_do_not_raise(self):
        # Bytes que no son UTF-8 válido ni tienen charset declarado: se
        # devuelve algo (con reemplazos) en vez de propagar una excepción y
        # perder el análisis entero.
        html = url_guard._decode_html(b"\xff\xfe roto \x81", _FakeResponse("text/html"))
        assert isinstance(html, str)


class TestCharsetFromContentType:
    def test_reads_declared_charset(self):
        assert url_guard._charset_from_content_type("text/html; charset=utf-8") == "utf-8"

    def test_strips_quotes(self):
        assert url_guard._charset_from_content_type('text/html; charset="utf-8"') == "utf-8"

    def test_returns_none_when_absent(self):
        # Clave del arreglo: "no declarado" tiene que ser distinguible de
        # "declarado latin-1", que es justo lo que `resp.encoding` confunde.
        assert url_guard._charset_from_content_type("text/html") is None

    def test_returns_none_for_missing_header(self):
        assert url_guard._charset_from_content_type(None) is None
