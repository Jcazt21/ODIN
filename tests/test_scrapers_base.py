"""Pruebas de los parsers puros de scrapers/base.py: `_parse_date` y
`_urls_from_sitemap`. Sin red, sin BD."""
from __future__ import annotations

from datetime import UTC

from scrapers.base import _parse_date, _urls_from_sitemap


class TestParseDate:
    def test_none_and_empty_return_none(self):
        assert _parse_date(None) is None
        assert _parse_date("") is None
        assert _parse_date("   ") is None

    def test_unparseable_string_returns_none(self):
        assert _parse_date("not a date") is None
        # separador no soportado ni por fromisoformat ni por los formatos strptime
        assert _parse_date("2026/01/15 10:30:00") is None

    def test_iso_with_offset_is_timezone_aware(self):
        result = _parse_date("2026-01-15T10:30:00-04:00")
        assert result is not None
        assert result.tzinfo is not None
        assert result.utcoffset().total_seconds() == -4 * 3600
        assert (result.hour, result.minute) == (10, 30)

    def test_iso_with_z_suffix_is_utc(self):
        result = _parse_date("2026-01-15T10:30:00Z")
        assert result is not None
        assert result.tzinfo == UTC

    def test_date_only_iso_is_naive(self):
        # Comportamiento actual (documentado como bug en task.md §2.7): una
        # fecha ISO sin hora/offset entra por la misma rama fromisoformat que
        # las fechas con offset, pero sale SIN tzinfo.
        result = _parse_date("2026-01-15")
        assert result is not None
        assert result.tzinfo is None
        assert (result.year, result.month, result.day) == (2026, 1, 15)

    def test_strips_surrounding_whitespace(self):
        result = _parse_date("  2026-01-15  ")
        assert result is not None
        assert (result.year, result.month, result.day) == (2026, 1, 15)

    def test_slash_format_falls_back_to_strptime_and_is_naive(self):
        result = _parse_date("15/01/2026")
        assert result is not None
        assert result.tzinfo is None
        assert (result.year, result.month, result.day) == (2026, 1, 15)

    def test_space_separated_iso_is_naive(self):
        result = _parse_date("2026-01-15 10:30:00")
        assert result is not None
        assert result.tzinfo is None
        assert (result.hour, result.minute) == (10, 30)


class TestUrlsFromSitemap:
    def test_extracts_locs_from_standard_sitemap(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url><loc>https://example.com/a</loc></url>
          <url><loc>https://example.com/b</loc></url>
        </urlset>"""
        assert _urls_from_sitemap(xml) == [
            "https://example.com/a",
            "https://example.com/b",
        ]

    def test_ignores_google_news_extension_elements(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
                xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
          <url>
            <loc>https://example.com/a</loc>
            <news:news><news:title>Titulo</news:title></news:news>
          </url>
        </urlset>"""
        assert _urls_from_sitemap(xml) == ["https://example.com/a"]

    def test_skips_empty_or_whitespace_only_loc(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url><loc>   </loc></url>
          <url><loc>https://example.com/b</loc></url>
        </urlset>"""
        assert _urls_from_sitemap(xml) == ["https://example.com/b"]

    def test_sitemap_index_returns_empty_not_nested_sitemaps(self):
        # Un índice de sitemaps anida <sitemap><loc>, no <url><loc>: debe
        # devolver vacío en vez de confundir sitemaps con artículos.
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <sitemap><loc>https://example.com/sitemap1.xml</loc></sitemap>
        </sitemapindex>"""
        assert _urls_from_sitemap(xml) == []

    def test_malformed_xml_returns_empty(self):
        assert _urls_from_sitemap("not xml at all <<<") == []

    def test_empty_string_returns_empty(self):
        assert _urls_from_sitemap("") == []
