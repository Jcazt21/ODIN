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
import threading
import time
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from urllib import robotparser
from urllib.parse import urlparse
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


# Los periódicos rastreados publican en hora de República Dominicana, que no
# observa horario de verano (UTC-4 todo el año) — a diferencia de otros países
# de la región, aquí un offset fijo es exacto, no una aproximación.
_SANTO_DOMINGO = timezone(timedelta(hours=-4))


def _parse_date(value: str | None) -> datetime | None:
    """Parsea la fecha que devuelve trafilatura (ISO 8601 o solo fecha) y la
    normaliza a UTC aware (§2.7 de task.md): sin esto, una fecha con offset
    ("...-04:00") y otra sin hora ("2026-01-15") llegaban una aware y otra
    naive a la misma columna `DateTime(timezone=True)`, con lo que Postgres y
    SQLite las interpretaban de forma distinta y los filtros de fecha de la
    API perdían artículos en los bordes del día.

    Cuando la fuente no da offset (fecha sola, o fecha+hora sin zona) se
    asume hora de Santo Domingo, que es de donde vienen todos los artículos.
    """
    if not value:
        return None
    value = value.strip()
    # datetime.fromisoformat (Py 3.11+) cubre ISO con hora, offset y 'Z'.
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        parsed = None
    if parsed is None:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
            try:
                parsed = datetime.strptime(value[:19], fmt)
                break
            except ValueError:
                continue
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_SANTO_DOMINGO)
    return parsed.astimezone(UTC)


class _DomainThrottle:
    """Cortesía real por dominio (§2.6 de task.md): garantiza al menos
    `settings.request_delay` segundos entre dos peticiones exitosas al mismo
    host, sin importar cuántos workers concurrentes las disparen.

    Antes `REQUEST_DELAY` solo se usaba como base del backoff en reintentos;
    con `fetch_workers` concurrentes contra el mismo dominio, el camino feliz
    no tenía ningún límite de tasa. Un lock por instancia (no un semáforo por
    dominio) es suficiente aquí: solo serializa el pequeño tramo "esperar mi
    turno", no la descarga en sí, así que sigue habiendo paralelismo real
    entre dominios distintos y con el resto de la descarga/extracción.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_request_at: dict[str, float] = {}

    def wait(self, domain: str, min_interval: float) -> None:
        if min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            last = self._last_request_at.get(domain)
            wait_for = 0.0 if last is None else (last + min_interval) - now
            # Reserva el turno ANTES de dormir (no después de la petición): así
            # dos threads que llegan casi a la vez para el mismo dominio se
            # espacian entre sí en vez de ambos ver "nadie ha pedido todavía".
            self._last_request_at[domain] = max(now, last or 0.0) + min_interval
        if wait_for > 0:
            time.sleep(wait_for)


class _RobotsCache:
    """`robots.txt` por dominio, descargado una vez y cacheado.

    Un dominio que no sirve robots.txt (404, timeout, sin conexión) se trata
    como "todo permitido" — es el comportamiento estándar del protocolo, y
    fallar cerrado dejaría de rastrear una fuente entera por un problema de
    red transitorio en un archivo opcional.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._parsers: dict[str, robotparser.RobotFileParser] = {}

    def _get_parser(self, domain: str) -> robotparser.RobotFileParser:
        with self._lock:
            parser = self._parsers.get(domain)
            if parser is not None:
                return parser
            parser = robotparser.RobotFileParser()
            parser.set_url(f"https://{domain}/robots.txt")
            try:
                parser.read()
            except Exception:
                # Sin robots.txt legible, se asume permitido (ver docstring).
                # atributo real en runtime; typeshed no lo declara en el stub.
                parser.allow_all = True  # type: ignore[attr-defined]
            self._parsers[domain] = parser
            return parser

    def can_fetch(self, url: str, user_agent: str) -> bool:
        domain = urlparse(url).netloc
        if not domain:
            return True
        return self._get_parser(domain).can_fetch(user_agent, url)

    def crawl_delay(self, url: str, user_agent: str) -> float | None:
        domain = urlparse(url).netloc
        if not domain:
            return None
        delay = self._get_parser(domain).crawl_delay(user_agent)
        return float(delay) if delay is not None else None


# Compartidos entre TODAS las instancias de scraper del proceso: el throttle
# solo tiene sentido si todo el mundo que le pega a un dominio pasa por el
# mismo reloj, y el cache de robots.txt evita re-descargarlo por instancia.
_domain_throttle = _DomainThrottle()
_robots_cache = _RobotsCache()


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
        """Descarga con reintentos y backoff exponencial ante errores de red.

        Antes de cada intento: respeta `robots.txt` (si el sitio nos excluye
        esa ruta, no se pide) y espera el turno del throttle por dominio
        (§2.6 de task.md) — el mismo intervalo, esté esto llamado desde un
        solo hilo o desde varios workers concurrentes contra el mismo host.
        """
        if settings.respect_robots_txt and not _robots_cache.can_fetch(url, settings.user_agent):
            log.info("bloqueado por robots.txt: %s", url)
            return None

        domain = urlparse(url).netloc
        min_interval = settings.request_delay
        if settings.respect_robots_txt:
            crawl_delay = _robots_cache.crawl_delay(url, settings.user_agent)
            if crawl_delay is not None:
                min_interval = max(min_interval, crawl_delay)

        retries = max(1, settings.fetch_retries)
        for attempt in range(retries):
            _domain_throttle.wait(domain, min_interval)
            try:
                resp = self.session.get(url, timeout=20)
                resp.raise_for_status()
                if "charset" not in resp.headers.get("content-type", "").lower():
                    # Sin charset en el header, requests asume ISO-8859-1 (RFC
                    # 2616) aunque el body sea UTF-8 (p. ej. acento.com.do) y
                    # los acentos llegan mojibake ("ediciÃ³n"). apparent_encoding
                    # (chardet) sí mira el contenido real.
                    resp.encoding = resp.apparent_encoding
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

    def scrape(
        self,
        limit: int | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> Iterator[ScrapedArticle]:
        """Genera artículos extraídos. La descarga se hace de forma concurrente
        (I/O de red), con un tope de workers como throttle de cortesía.

        `should_stop()`, si se pasa, se consulta después de cada URL bajada
        (no solo antes/después de la fuente entera, que en un sitemap grande
        como el de Listín Diario tarda varios minutos — sin este chequeo
        intermedio, cancelar una corrida podía tardar lo mismo que la fuente
        más lenta). Al cortar, no se espera a los workers en vuelo: se
        cancelan las tareas todavía en cola (`cancel_futures=True`) y las que
        ya estaban en curso simplemente terminan solas en segundo plano, sin
        que nadie consuma su resultado.
        """
        urls = self.discover_urls(limit=limit)
        if not urls:
            log.info("%s: no se descubrió ninguna URL", self.name)
            return
        log.info(
            "%s: %d URLs descubiertas, descargando con %d workers (~%.1fs entre "
            "peticiones al mismo dominio, puede tardar)",
            self.name,
            len(urls),
            max(1, settings.fetch_workers),
            settings.request_delay,
        )
        workers = max(1, settings.fetch_workers)
        completed = 0
        progress_every = max(1, len(urls) // 10)  # ~10 avisos por fuente, sea grande o chica
        pool = ThreadPoolExecutor(max_workers=workers)
        try:
            futures = {pool.submit(self._fetch_and_extract, u): u for u in urls}
            for future in as_completed(futures):
                completed += 1
                if completed % progress_every == 0 or completed == len(urls):
                    log.info("%s: descargadas %d/%d", self.name, completed, len(urls))
                try:
                    article = future.result()
                except Exception:
                    log.exception("error procesando %s", futures[future])
                    continue
                if article is not None:
                    yield article
                if should_stop is not None and should_stop():
                    log.info("%s: cancelado, %d/%d procesadas", self.name, completed, len(urls))
                    return
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
