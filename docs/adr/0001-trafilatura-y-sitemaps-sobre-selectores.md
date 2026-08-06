# ADR-001: `trafilatura` + sitemaps/RSS en lugar de selectores CSS por portada

## Status
Accepted

## Date
2026-08-05 (decisión original tomada antes del primer commit; formalizada retroactivamente — ver `task.md` §1)

## Context
Odin necesita descubrir URLs de artículos nuevos en 8 medios dominicanos y
extraer su contenido (título, cuerpo, autor, fecha). Los sitios de noticias
cambian su HTML con frecuencia (rediseños, A/B tests, anuncios), y cada medio
tiene su propia estructura de portada.

## Decision
- **Descubrimiento** por sitemap XML o feed RSS (`scrapers/base.py`), no por
  scraping de la portada con selectores CSS. Agregar un medio nuevo es heredar
  de `BaseScraper` y declarar `feeds`/`sitemaps` (`scrapers/do_scrapers.py`).
- **Extracción** de contenido con `trafilatura.extract(output_format="json",
  with_metadata=True)` (heurística genérica de extracción de artículo), en vez
  de selectores CSS por medio (`article.body`, `.entry-content`, etc.).

## Alternatives Considered

### Selectores CSS por medio (BeautifulSoup + XPath/CSS por sitio)
- Pros: control total sobre qué texto se extrae, cero dependencia externa.
- Cons: un rediseño del medio rompe el scraper sin aviso; agregar un medio
  nuevo requiere inspeccionar su HTML e implementar selectores a mano.
- Rejected: la superficie de mantenimiento crece linealmente con cada medio y
  con cada rediseño de cada medio — inviable para 8+ fuentes con un solo
  mantenedor.

### Scraping de portada para descubrimiento
- Pros: no depende de que el medio mantenga un sitemap/feed correcto.
- Cons: la portada es la parte más inestable del HTML (banners, secciones
  dinámicas, paginación por JS).
- Rejected como regla general, **excepto** para Acento
  (`scrapers/do_scrapers.py`), el único de los 8 medios sin sitemap ni RSS
  fiable — ahí se acepta el costo de mantenimiento como excepción documentada,
  no como patrón a extender a otros medios.

## Consequences
- Agregar un medio nuevo cuesta ~4 líneas cuando tiene sitemap/RSS
  (`task.md` §1), un scraper completo (con su propio parseo) cuando no lo
  tiene (caso Acento).
- `trafilatura` puede fallar en extraer artículos con estructura muy atípica
  (galerías, liveblogs); el fallback es `None` y el artículo se descarta
  silenciosamente hoy (gap de observabilidad, ver `task.md` §2.3 — no resuelto
  por este ADR).
- Actualizar `trafilatura` puede cambiar el texto extraído de artículos ya
  analizados sin que quede registro, porque el HTML crudo no se conserva
  (`task.md` §2.2 — gap conocido, no resuelto por este ADR).
