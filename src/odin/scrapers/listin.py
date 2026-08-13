"""Scraper de Listín Diario.

Listín Diario no expone RSS, pero sí un sitemap de Google News con los
artículos más recientes y su metadata. Descubrimos las URLs desde ahí y luego
extraemos el contenido con trafilatura (flujo estándar de BaseScraper).
"""
from __future__ import annotations

from odin.scrapers.base import BaseScraper


class ListinDiarioScraper(BaseScraper):
    source = "listin_diario"
    name = "Listín Diario"
    sitemaps = ["https://listindiario.com/sitemap-google-news.xml"]
