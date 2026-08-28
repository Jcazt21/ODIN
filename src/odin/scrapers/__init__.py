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
]
