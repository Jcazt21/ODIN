from functools import lru_cache
from urllib.parse import urlparse

from odin.scrapers.authors import strip_outlet
from odin.scrapers.base import BaseScraper, ScrapedArticle
from odin.scrapers.diario_libre import DiarioLibreScraper
from odin.scrapers.do_scrapers import (
    AcentoScraper,
    AlMomentoScraper,
    ElCaribeScraper,
    ElDiaScraper,
    ElNacionalScraper,
    HoyScraper,
    NDigitalScraper,
)
from odin.scrapers.listin import ListinDiarioScraper

# Registro de scrapers disponibles, por clave de fuente.
SCRAPERS: dict[str, type[BaseScraper]] = {
    ListinDiarioScraper.source: ListinDiarioScraper,
    DiarioLibreScraper.source: DiarioLibreScraper,
    ElNacionalScraper.source: ElNacionalScraper,
    HoyScraper.source: HoyScraper,
    ElCaribeScraper.source: ElCaribeScraper,
    AlMomentoScraper.source: AlMomentoScraper,
    ElDiaScraper.source: ElDiaScraper,
    NDigitalScraper.source: NDigitalScraper,
    AcentoScraper.source: AcentoScraper,
}



@lru_cache(maxsize=1)
def _domain_to_source() -> dict[str, str]:
    """Dominio -> clave del medio.

    Se deduce de los feeds y sitemaps que el scraper ya usa, para no mantener
    los dominios en un segundo lugar que el día de mañana quede apuntando al
    dominio viejo. Pero la deducción no siempre alcanza: un scraper que arma
    las URLs desde la portada no tiene feeds, y por eso existe `domains`, que
    se declara solo en ese caso. El test de cobertura avisa si alguno queda
    sin alcanzar por ninguna de las dos vías.
    """
    mapping: dict[str, str] = {}
    for slug, scraper in SCRAPERS.items():
        derived = [urlparse(u).netloc for u in list(scraper.feeds) + list(scraper.sitemaps)]
        for host in list(scraper.domains) + derived:
            host = host.lower().removeprefix("www.")
            if host:
                mapping.setdefault(host, slug)
    return mapping


def source_from_url(url: str) -> str | None:
    """Clave del medio a partir del dominio, o `None` si no se reconoce.

    Se usa al analizar una URL suelta: antes el medio salía de lo que detectara
    trafilatura y, si no detectaba nada, quedaba como "manual" —un valor que no
    es un medio y que ensuciaba la dimensión por la que el cliente filtra. El
    dominio, en cambio, ya está en la URL y no depende de la extracción.

    Devuelve `None` en vez de adivinar: para un medio que no rastreamos, es
    mejor que quien llama decida qué guardar a inventar una clave que después
    aparecería en los filtros como si fuera un medio conocido.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https"):
        return None
    host = parsed.netloc.lower().removeprefix("www.")
    return _domain_to_source().get(host)



def strip_outlet_from_authors(authors: str | None, source: str) -> str | None:
    """Quita el nombre del medio del campo de autores. Ver `authors.strip_outlet`.

    Reconoce el nombre legible del registro ("Listín Diario"), el slug
    (`listin_diario`) y el slug con espacios, porque los sitios se identifican
    de las tres formas.
    """
    names = {source, source.replace("_", " ")}
    scraper = SCRAPERS.get(source)
    if scraper is not None:
        names.add(scraper.name)
        # Los dominios también: hay sitios que se firman con el suyo.
        names |= {d for d, slug in _domain_to_source().items() if slug == source}
    return strip_outlet(authors, names)


def source_name(source: str) -> str:
    """Nombre legible del medio a partir del slug guardado en `articles.source`.

    Los nombres no se listan aquí: cada scraper ya declara el suyo junto al
    slug (`ListinDiarioScraper.source` / `.name`), y duplicarlos garantizaría
    que un día dejen de coincidir.

    Un slug fuera del registro —reporte cargado a mano, scraper retirado— cae
    a una forma presentable en vez del crudo: en pantalla "Diario X" dice lo
    mismo que `diario_x` sin parecer un error.
    """
    if not source:
        return ""
    scraper = SCRAPERS.get(source)
    if scraper is not None:
        return scraper.name
    return source.replace("_", " ").title()


__all__ = [
    "BaseScraper",
    "ScrapedArticle",
    "ListinDiarioScraper",
    "DiarioLibreScraper",
    "ElNacionalScraper",
    "HoyScraper",
    "ElCaribeScraper",
    "AlMomentoScraper",
    "ElDiaScraper",
    "NDigitalScraper",
    "AcentoScraper",
    "SCRAPERS",
    "source_name",
    "source_from_url",
    "strip_outlet_from_authors",
]
