"""Pruebas de los parsers puros de scrapers/base.py: `_parse_date` y
`_urls_from_sitemap`; y del throttle por dominio + robots.txt de §2.6 de
task.md (`_DomainThrottle`, `_RobotsCache`, `BaseScraper.fetch`). Sin red real,
sin BD."""
from __future__ import annotations

import time
from datetime import UTC
from urllib import robotparser

from scrapers.base import (
    BaseScraper,
    _DomainThrottle,
    _parse_date,
    _RobotsCache,
    _urls_from_sitemap,
)


class TestParseDate:
    def test_none_and_empty_return_none(self):
        assert _parse_date(None) is None
        assert _parse_date("") is None
        assert _parse_date("   ") is None

    def test_unparseable_string_returns_none(self):
        assert _parse_date("not a date") is None
        # separador no soportado ni por fromisoformat ni por los formatos strptime
        assert _parse_date("2026/01/15 10:30:00") is None

    def test_iso_with_offset_is_normalized_to_utc(self):
        result = _parse_date("2026-01-15T10:30:00-04:00")
        assert result is not None
        assert result.tzinfo == UTC
        assert (result.hour, result.minute) == (14, 30)

    def test_iso_with_z_suffix_is_utc(self):
        result = _parse_date("2026-01-15T10:30:00Z")
        assert result is not None
        assert result.tzinfo == UTC
        assert (result.hour, result.minute) == (10, 30)

    def test_date_only_iso_assumes_santo_domingo_and_converts_to_utc(self):
        # §2.7 de task.md: una fecha sin offset se asume en hora de Santo
        # Domingo (UTC-4 fijo, sin horario de verano) y se normaliza a UTC
        # aware — nunca naive, aunque la fuente no diera zona.
        result = _parse_date("2026-01-15")
        assert result is not None
        assert result.tzinfo == UTC
        assert (result.year, result.month, result.day, result.hour) == (2026, 1, 15, 4)

    def test_strips_surrounding_whitespace(self):
        result = _parse_date("  2026-01-15  ")
        assert result is not None
        assert result.tzinfo == UTC
        assert (result.year, result.month, result.day) == (2026, 1, 15)

    def test_slash_format_falls_back_to_strptime_and_assumes_santo_domingo(self):
        result = _parse_date("15/01/2026")
        assert result is not None
        assert result.tzinfo == UTC
        assert (result.year, result.month, result.day, result.hour) == (2026, 1, 15, 4)

    def test_space_separated_iso_assumes_santo_domingo(self):
        result = _parse_date("2026-01-15 10:30:00")
        assert result is not None
        assert result.tzinfo == UTC
        assert (result.hour, result.minute) == (14, 30)


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


class TestDomainThrottle:
    def test_first_request_to_a_domain_does_not_wait(self):
        throttle = _DomainThrottle()
        started = time.monotonic()
        throttle.wait("example.com", min_interval=1.0)
        assert time.monotonic() - started < 0.1

    def test_second_request_to_same_domain_waits_the_remaining_interval(self):
        throttle = _DomainThrottle()
        throttle.wait("example.com", min_interval=0.2)
        started = time.monotonic()
        throttle.wait("example.com", min_interval=0.2)
        assert time.monotonic() - started >= 0.15  # margen bajo timers de CI

    def test_different_domains_do_not_throttle_each_other(self):
        throttle = _DomainThrottle()
        throttle.wait("a.com", min_interval=5.0)
        started = time.monotonic()
        throttle.wait("b.com", min_interval=5.0)
        assert time.monotonic() - started < 0.1

    def test_zero_interval_never_waits(self):
        throttle = _DomainThrottle()
        throttle.wait("example.com", min_interval=0.0)
        started = time.monotonic()
        throttle.wait("example.com", min_interval=0.0)
        assert time.monotonic() - started < 0.1


class TestRobotsCache:
    def _cache_with_fake_parser(self, monkeypatch, *, disallow: list[str] | None = None, crawl_delay: float | None = None):
        cache = _RobotsCache()

        def _fake_get_parser(self, domain):
            parser = robotparser.RobotFileParser()
            lines = ["User-agent: *"]
            for path in disallow or []:
                lines.append(f"Disallow: {path}")
            if not disallow:
                lines.append("Disallow:")
            if crawl_delay is not None:
                lines.append(f"Crawl-delay: {crawl_delay}")
            parser.parse(lines)
            return parser

        monkeypatch.setattr(_RobotsCache, "_get_parser", _fake_get_parser)
        return cache

    def test_allows_url_not_disallowed(self, monkeypatch):
        cache = self._cache_with_fake_parser(monkeypatch, disallow=["/admin/"])
        assert cache.can_fetch("https://example.com/articulo-1", "OdinNewsBot/1.0") is True

    def test_blocks_disallowed_path(self, monkeypatch):
        cache = self._cache_with_fake_parser(monkeypatch, disallow=["/admin/"])
        assert cache.can_fetch("https://example.com/admin/panel", "OdinNewsBot/1.0") is False

    def test_reads_crawl_delay(self, monkeypatch):
        cache = self._cache_with_fake_parser(monkeypatch, crawl_delay=3)
        assert cache.crawl_delay("https://example.com/x", "OdinNewsBot/1.0") == 3.0

    def test_no_crawl_delay_returns_none(self, monkeypatch):
        cache = self._cache_with_fake_parser(monkeypatch)
        assert cache.crawl_delay("https://example.com/x", "OdinNewsBot/1.0") is None

    def test_unreachable_robots_txt_defaults_to_allowed(self, monkeypatch):
        cache = _RobotsCache()

        def _raise_on_read(self):
            raise OSError("network unreachable")

        monkeypatch.setattr(robotparser.RobotFileParser, "read", _raise_on_read)
        assert cache.can_fetch("https://example.com/cualquier-cosa", "OdinNewsBot/1.0") is True

    def test_caches_parser_per_domain(self, monkeypatch):
        # `read()` real solo se dispara la primera vez que se ve un dominio;
        # la segunda consulta reutiliza el parser ya cacheado.
        monkeypatch.setattr(robotparser.RobotFileParser, "read", lambda self: None)
        cache = _RobotsCache()
        cache.can_fetch("https://example.com/a", "bot")
        cache.can_fetch("https://example.com/b", "bot")
        assert len(cache._parsers) == 1


class TestFetchRespectsRobotsAndThrottle:
    def _patch_settings(self, monkeypatch, base_module, **overrides):
        # Settings es un dataclass frozen: no se puede mutar un campo, hay
        # que reemplazar el objeto `settings` completo del módulo.
        import dataclasses

        monkeypatch.setattr(base_module, "settings", dataclasses.replace(base_module.settings, **overrides))

    def test_fetch_skips_disallowed_url(self, monkeypatch):
        import scrapers.base as base_module

        self._patch_settings(monkeypatch, base_module, respect_robots_txt=True)
        monkeypatch.setattr(base_module._robots_cache, "can_fetch", lambda url, ua: False)

        scraper = BaseScraper()
        called = False

        def _fail_if_called(*args, **kwargs):
            nonlocal called
            called = True
            raise AssertionError("no debería llamar a session.get si robots.txt lo prohíbe")

        monkeypatch.setattr(scraper.session, "get", _fail_if_called)
        result = scraper.fetch("https://example.com/bloqueado")
        assert result is None
        assert called is False

    def test_fetch_waits_for_domain_throttle(self, monkeypatch):
        import scrapers.base as base_module

        self._patch_settings(monkeypatch, base_module, respect_robots_txt=False, request_delay=0.2)

        scraper = BaseScraper()

        class _FakeResponse:
            text = "ok"

            def raise_for_status(self):
                pass

        monkeypatch.setattr(scraper.session, "get", lambda url, timeout: _FakeResponse())

        # Throttle limpio para este test (es un singleton de módulo compartido
        # entre todas las instancias de BaseScraper).
        fresh_throttle = _DomainThrottle()
        monkeypatch.setattr(base_module, "_domain_throttle", fresh_throttle)

        scraper.fetch("https://example.com/a")
        started = time.monotonic()
        scraper.fetch("https://example.com/a")
        assert time.monotonic() - started >= 0.15

    def test_fetch_uses_crawl_delay_when_larger_than_request_delay(self, monkeypatch):
        import scrapers.base as base_module

        self._patch_settings(monkeypatch, base_module, respect_robots_txt=True, request_delay=0.05)
        monkeypatch.setattr(base_module._robots_cache, "can_fetch", lambda url, ua: True)
        monkeypatch.setattr(base_module._robots_cache, "crawl_delay", lambda url, ua: 0.3)

        scraper = BaseScraper()

        class _FakeResponse:
            text = "ok"

            def raise_for_status(self):
                pass

        monkeypatch.setattr(scraper.session, "get", lambda url, timeout: _FakeResponse())

        fresh_throttle = _DomainThrottle()
        monkeypatch.setattr(base_module, "_domain_throttle", fresh_throttle)

        scraper.fetch("https://example.com/a")
        started = time.monotonic()
        scraper.fetch("https://example.com/a")
        assert time.monotonic() - started >= 0.25
