"""Scrapers de periódicos dominicanos (descubrimiento por sitemap o RSS).

Todos reutilizan el flujo estándar de BaseScraper: descubrir URLs desde
`sitemaps`/`feeds` y extraer el contenido con trafilatura.

URLs de descubrimiento verificadas el 2026-08-02:
  elnacional.com.do  → sitemap Google News (~136 artículos)
  hoy.com.do         → sitemap Google News (~185 artículos)
  elcaribe.com.do    → news-sitemap.xml   (~127 artículos)
  almomento.net      → RSS (~20 entradas)
  eldia.com.do       → RSS (~15 entradas)
  n.com.do           → RSS (~10 entradas)

Medios descartados (por ahora):
  - Acento (acento.com.do): el feed RSS devuelve HTML 200 vacío; sin sitemap
    público. Necesita scraping directo de la portada o API privada.
"""
from __future__ import annotations

from scrapers.base import BaseScraper


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
    feeds = ["https://eldia.com.do/feed/"]


class NDigitalScraper(BaseScraper):
    source = "n_digital"
    name = "N Digital"
    feeds = ["https://n.com.do/feed/"]
