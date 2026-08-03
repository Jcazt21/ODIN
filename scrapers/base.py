"""Scraper base para periódicos.

Estrategia general (funciona para la mayoría de periódicos sin selectores frágiles):
  1. Descubrir URLs de artículos a partir de feeds RSS y/o sitemaps de noticias.
  2. Descargar cada artículo y extraer título/cuerpo/autor/fecha con `trafilatura`.

Para agregar un periódico nuevo basta con heredar de BaseScraper y definir
`source`, `name` y `feeds` y/o `sitemaps`. Si un sitio necesita lógica especial,
se sobreescribe `discover_urls()` o `extract()`.
"""
from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from xml.etree import ElementTree as ET

import feedparser
import requests
import trafilatura

from config import settings

log = logging.getLogger("odin.scraper")

_SM_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


def _urls_from_sitemap(xml: str) -> list[str]:
    """Extrae los <loc> de artículos de un sitemap XML (estándar o Google News).

    Solo mira `<url><loc>`, no `<sitemap><loc>`: si el sitio sirve un índice de
    sitemaps en vez de un sitemap de artículos, devolvemos vacío en lugar de
    confundir sitemaps anidados con artículos.
    """
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return []
    return [
        loc.text.strip()
        for loc in root.findall(f"{_SM_NS}url/{_SM_NS}loc")
        if loc.text and loc.text.strip()
    ]


def _parse_date(value: str | None) -> datetime | None:
    """Parsea la fecha que devuelve trafilatura (ISO 8601 o solo fecha)."""
    if not value:
        return None
    value = value.strip()
    # datetime.fromisoformat (Py 3.11+) cubre ISO con hora, offset y 'Z'.
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value[:19], fmt)
        except ValueError:
            continue
    return None


@dataclass
class ScrapedArticle:
    """Datos crudos extraídos de un artículo, antes del análisis NLP."""

    source: str
    url: str
    title: str
    body: str
    authors: str | None = None
    section: str | None = None
    published_at: datetime | None = None
    _raw: dict = field(default_factory=dict, repr=False)


class BaseScraper:
    #: clave corta y estable para la fuente (se guarda en la BD)
    source: str = ""
    #: nombre legible
    name: str = ""
    #: lista de URLs de feeds RSS a rastrear
    feeds: list[str] = []
    #: lista de sitemaps de noticias (estándar o Google News) a rastrear
    sitemaps: list[str] = []

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": settings.user_agent})

    # ---- Descubrimiento de URLs -------------------------------------------------
    def discover_urls(self, limit: int | None = None) -> list[str]:
        """Devuelve URLs de artículos a partir de `sitemaps` y `feeds`.

        Los feeds se descargan con `self.fetch()` (User-Agent propio, reintentos
        y backoff) en vez de dejar que feedparser haga la petición: algunos
        sitios rechazan el User-Agent por defecto de feedparser y devuelven
        HTML en lugar de XML.
        """
        urls: list[str] = []
        seen: set[str] = set()

        def _add(link: str | None) -> bool:
            """Añade el link (deduplicado); True si ya alcanzamos el límite."""
            if link and link not in seen:
                seen.add(link)
                urls.append(link)
            return limit is not None and limit > 0 and len(urls) >= limit

        for sitemap_url in self.sitemaps:
            xml = self.fetch(sitemap_url)
            for link in _urls_from_sitemap(xml) if xml else []:
                if _add(link):
                    return urls

        for feed_url in self.feeds:
            text = self.fetch(feed_url)
            if not text:
                continue
            for entry in feedparser.parse(text).entries:
                if _add(getattr(entry, "link", None)):
                    return urls
        return urls

    # ---- Descarga + extracción --------------------------------------------------
    def fetch(self, url: str) -> str | None:
        """Descarga con reintentos y backoff exponencial ante errores de red."""
        retries = max(1, settings.fetch_retries)
        for attempt in range(retries):
            try:
                resp = self.session.get(url, timeout=20)
                resp.raise_for_status()
                return resp.text
            except requests.RequestException as exc:
                if attempt + 1 >= retries:
                    log.warning("fetch falló (%s): %s", url, exc)
                    return None
                time.sleep(settings.request_delay * (2**attempt))
        return None

    def extract(self, url: str, html: str) -> ScrapedArticle | None:
        """Extrae los campos del artículo usando trafilatura."""
        data = trafilatura.extract(
            html,
            output_format="json",
            with_metadata=True,
            include_comments=False,
            url=url,
        )
        if not data:
            return None

        meta = json.loads(data)
        body = (meta.get("text") or "").strip()
        title = (meta.get("title") or "").strip()
        if not body or not title:
            return None

        authors = meta.get("author") or None
        section = None
        cats = meta.get("categories")
        if cats:
            section = cats[0] if isinstance(cats, list) else str(cats)

        published_at = _parse_date(meta.get("date"))

        return ScrapedArticle(
            source=self.source,
            url=url,
            title=title,
            body=body,
            authors=authors,
            section=section,
            published_at=published_at,
            _raw=meta,
        )

    # ---- Orquestación -----------------------------------------------------------
    def _fetch_and_extract(self, url: str) -> ScrapedArticle | None:
        html = self.fetch(url)
        return self.extract(url, html) if html else None

    def scrape(self, limit: int | None = None) -> Iterator[ScrapedArticle]:
        """Genera artículos extraídos. La descarga se hace de forma concurrente
        (I/O de red), con un tope de workers como throttle de cortesía."""
        urls = self.discover_urls(limit=limit)
        if not urls:
            return
        workers = max(1, settings.fetch_workers)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(self._fetch_and_extract, u): u for u in urls}
            for future in as_completed(futures):
                try:
                    article = future.result()
                except Exception:
                    log.exception("error procesando %s", futures[future])
                    continue
                if article is not None:
                    yield article
