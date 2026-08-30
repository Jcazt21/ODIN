"""Scrapers de periódicos dominicanos (descubrimiento por sitemap o RSS).

La mayoría reutiliza el flujo estándar de BaseScraper: descubrir URLs desde
`sitemaps`/`feeds` y extraer el contenido con trafilatura.

URLs de descubrimiento verificadas el 2026-08-02:
  elnacional.com.do  → sitemap Google News (~136 artículos)
  hoy.com.do         → sitemap Google News (~185 artículos)
  elcaribe.com.do    → news-sitemap.xml   (~127 artículos)
  almomento.net      → RSS (~20 entradas)
  eldia.com.do       → RSS (~15 entradas)
  n.com.do           → RSS (~10 entradas)

Verificado el 2026-08-04:
  acento.com.do      → portada (~80 artículos), ver AcentoScraper
"""
from __future__ import annotations

import re

from odin.scrapers.base import BaseScraper


class ElNacionalScraper(BaseScraper):
    source = "el_nacional"
    name = "El Nacional"
    sitemaps = ["https://elnacional.com.do/sitemap-google-news.xml"]


class HoyScraper(BaseScraper):
    # La portada de hoy.com.do tiene redirecciones excesivas, pero el sitemap
    # responde directamente sin redirigir.
    source = "hoy"
    name = "Hoy"
    sitemaps = ["https://hoy.com.do/sitemap-google-news.xml"]


class ElCaribeScraper(BaseScraper):
    source = "el_caribe"
    name = "El Caribe"
    sitemaps = ["https://www.elcaribe.com.do/news-sitemap.xml"]


class AlMomentoScraper(BaseScraper):
    source = "al_momento"
    name = "Al Momento"
    feeds = ["https://almomento.net/feed/"]

    def discover_urls(self, limit: int | None = None) -> list[str]:
        # El feed publica los links como http://; el sitio redirige a https://.
        # Normalizamos para que la misma URL no entre dos veces a la BD.
        return [
            url.replace("http://", "https://", 1) if url.startswith("http://") else url
            for url in super().discover_urls(limit=limit)
        ]


class ElDiaScraper(BaseScraper):
    source = "el_dia"
    name = "El Día"
    # Sin slash final a propósito: el robots.txt del sitio tiene
    # "Disallow: */feed/" pero "Allow: /feed$" — con el slash, _RobotsCache
    # lo bloquea entero y discover_urls() no encuentra nada.
    feeds = ["https://eldia.com.do/feed"]


class NDigitalScraper(BaseScraper):
    source = "n_digital"
    name = "N Digital"
    feeds = ["https://n.com.do/feed/"]


_ACENTO_ARTICLE_RE = re.compile(r"https://acento\.com\.do/[a-z0-9-]+/[a-z0-9-]+-\d+\.html")


class AcentoScraper(BaseScraper):
    """Acento no tiene una fuente de descubrimiento estándar: el feed RSS
    devuelve HTML 200 vacío, `sitemaps-daily.xml` solo lista páginas de
    sección (no artículos) y `sitemaps-index.xml` apunta a listados .txt
    desactualizados (última actualización 2025-03-05). En cambio, la portada
    trae los links de artículo directo en el HTML
    (`/<sección>/<slug>-<id numérico>.html`), así que los extraemos por regex.
    """

    source = "acento"
    name = "Acento"
    domains = ["acento.com.do"]

    def discover_urls(self, limit: int | None = None) -> list[str]:
        html = self.fetch("https://acento.com.do/")
        if not html:
            return []
        urls = list(dict.fromkeys(_ACENTO_ARTICLE_RE.findall(html)))
        if limit is not None and limit > 0:
            urls = urls[:limit]
        return urls
