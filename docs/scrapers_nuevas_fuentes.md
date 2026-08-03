# Agregar más scrapers dominicanos a Odin

Guía de referencia para añadir nuevas fuentes siguiendo el patrón de
`scrapers/base.py`. Cada medio nuevo = un archivo `scrapers/<clave>.py`
con una clase que hereda de `BaseScraper` + una línea en `scrapers/__init__.py`.

---

## Patrón mínimo

```python
# scrapers/mi_medio.py
from scrapers.base import BaseScraper

class MiMedioScraper(BaseScraper):
    source = "mi_medio"        # clave en BD
    name   = "Mi Medio"
    feeds  = ["https://mimedio.com.do/feed/"]   # si tiene RSS
```

```python
# scrapers/__init__.py — añadir:
from scrapers.mi_medio import MiMedioScraper
SCRAPERS["mi_medio"] = MiMedioScraper
```

Si el sitio **no tiene RSS** pero sí sitemap, usar `discover_urls()`:

```python
from xml.etree import ElementTree as ET
_SM_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"

class MiMedioScraper(BaseScraper):
    source = "mi_medio"
    name   = "Mi Medio"
    feeds  = []
    _SITEMAP = "https://mimedio.com.do/news-sitemap.xml"

    def discover_urls(self, limit=None):
        html = self.fetch(self._SITEMAP)
        if not html:
            return []
        root = ET.fromstring(html)
        urls = [el.text.strip() for el in root.iter(f"{_SM_NS}loc") if el.text]
        return urls[:limit] if limit else urls
```

Si el RSS requiere el **User-Agent de Odin** para responder XML
(como N Digital), usar `self.fetch()` + `feedparser.parse(text)`:

```python
def discover_urls(self, limit=None):
    import feedparser
    html = self.fetch("https://mimedio.com.do/feed/")
    parsed = feedparser.parse(html or "")
    urls = [e.link for e in parsed.entries if getattr(e, "link", None)]
    return urls[:limit] if limit else urls
```

---

## Fuentes pendientes — estado investigado

### Acento (`acento.com.do`) ⚠️ requiere trabajo extra

| URL probada | Resultado |
|---|---|
| `/?feed=rss2` | 200 pero devuelve HTML (sin XML) |
| `/news-sitemap.xml` | 404 |
| `/sitemap-google-news.xml` | 404 |
| `/sitemap.xml` | 404 |

**Acento bloqueó o eliminó sus feeds públicos.** Opciones:

1. **Scraping de la portada** — parsear `https://acento.com.do/` con
   BeautifulSoup, extraer todos los `<a href>` que apunten a rutas de
   artículo (ej. `/YYYY/MM/DD/...` o `/noticias/...`) y filtrar por patrón.
2. **Google News RSS** — `https://news.google.com/rss/search?q=site:acento.com.do&hl=es-419&gl=DO`
   devuelve los artículos de Acento indexados en Google News.
   No requiere ningún permiso del sitio y es completamente público.

La opción 2 es la más limpia para implementar:

```python
class AcentoScraper(BaseScraper):
    source = "acento"
    name   = "Acento"
    feeds  = [
        "https://news.google.com/rss/search"
        "?q=site:acento.com.do&hl=es-419&gl=DO&ceid=DO:es-419"
    ]
```

> ⚠️ Las URLs que devuelve Google News son redirects (`news.google.com/rss/articles/...`).
> Hay que resolver el redirect con `follow_redirects=True` en `self.fetch()` o
> usar `requests.get(..., allow_redirects=True)` para llegar a la URL real
> antes de extraer con trafilatura.

---

### El Nuevo Diario (`elnuevodiario.com.do`) ✅ listo para implementar

| Mecanismo | URL | Artículos |
|---|---|---|
| RSS | `https://elnuevodiario.com.do/feed/` | 10 por ciclo |
| news-sitemap.xml | `https://elnuevodiario.com.do/news-sitemap.xml` | 449 |

Recomendado: usar el `news-sitemap.xml` para mayor cobertura.

```python
# scrapers/el_nuevo_diario.py
from xml.etree import ElementTree as ET
from scrapers.base import BaseScraper

_SM_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"

class ElNuevoDiarioScraper(BaseScraper):
    source   = "el_nuevo_diario"
    name     = "El Nuevo Diario"
    feeds    = []
    _SITEMAP = "https://elnuevodiario.com.do/news-sitemap.xml"

    def discover_urls(self, limit=None):
        html = self.fetch(self._SITEMAP)
        if not html:
            return []
        root = ET.fromstring(html)
        urls = [el.text.strip() for el in root.iter(f"{_SM_NS}loc") if el.text]
        return urls[:limit] if limit else urls
```

---

### Noticias SIN (`noticiassin.com`) ✅ listo para implementar

| Mecanismo | URL | Artículos |
|---|---|---|
| RSS | `https://noticiassin.com/feed/` | 10 por ciclo |
| news-sitemap.xml | 404 |

Solo RSS disponible. El servidor responde con `content-type: text/xml`
(no `application/rss+xml`) pero el contenido es RSS válido.

```python
# scrapers/sin.py
from scrapers.base import BaseScraper

class NoticiasSinScraper(BaseScraper):
    source = "noticias_sin"
    name   = "Noticias SIN"
    feeds  = ["https://noticiassin.com/feed/"]
```

---

### El Caribe (`elcaribe.com.do`) ✅ ya implementado en `_draft_do_scrapers.py`

news-sitemap.xml funciona, ~127 artículos. Ver `ElCaribeScraper`.

---

## Checklist para integrar cualquier medio nuevo

```
[ ] Crear scrapers/<clave>.py con la clase
[ ] Probar discover_urls(limit=5) de forma aislada
[ ] Probar extract() sobre una URL real (verifica que trafilatura la lea)
[ ] Añadir import y entrada a SCRAPERS en scrapers/__init__.py
[ ] Añadir <clave> al registro de scrapers en main.py / pipeline.py si aplica
```

---

## Por qué más fuentes importa

Cada artículo guardado es un ejemplo etiquetado (sentimiento + entidades
ya revisadas) que puede usarse para fine-tuning de un modelo propio.
Con ≥50k artículos de prensa dominicana se podría entrenar/ajustar:

- Un modelo de sentimiento especializado en español dominicano
  (el vocabulario político local difiere del español estándar).
- Un NER más preciso para personas y organizaciones locales
  (siglas, apellidos compuestos, nombres de partidos).

Fuentes actuales + 4 nuevas = cobertura ~10 medios, estimado ~500 artículos/día.
