from scrapers.base import BaseScraper, ScrapedArticle
from scrapers.diario_libre import DiarioLibreScraper
from scrapers.do_scrapers import (
    AcentoScraper,
    AlMomentoScraper,
    ElCaribeScraper,
    ElDiaScraper,
    ElNacionalScraper,
    HoyScraper,
    NDigitalScraper,
)
from scrapers.listin import ListinDiarioScraper

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
]
