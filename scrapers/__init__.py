from scrapers.base import BaseScraper, ScrapedArticle
from scrapers.listin import ListinDiarioScraper
from scrapers.diario_libre import DiarioLibreScraper
from scrapers.do_scrapers import (
    AlMomentoScraper,
    ElCaribeScraper,
    ElDiaScraper,
    ElNacionalScraper,
    HoyScraper,
    NDigitalScraper,
)

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
    "SCRAPERS",
]
