# Odin — Scraping y análisis de periódicos dominicanos

Odin rastrea **Listín Diario** y **Diario Libre**, lee cada artículo, lo analiza
y guarda en una base de datos:

- **Autor**, **título**, **fecha**, **sección**, **cuerpo**, **URL**, **fuente**
- **De qué se habla**: tema principal + palabras clave
- **Sentimiento global**: `POS` / `NEG` / `NEU` (bueno / malo / neutro)
- **Figuras públicas y empresas** mencionadas
- **Opinión hacia cada figura/empresa**: si hablan bien, mal o neutro de ella

El análisis usa por defecto **modelos locales gratis** (spaCy + pysentimiento en
español), sin API de pago.

---

## Stack tecnológico

**Backend**
- **Python 3.12/3.13** — Python 3.12 en Docker (`Dockerfile.backend`); Python 3.13 recomendado en local (ver [Instalación](#instalación))
- **FastAPI** + **Uvicorn** — API HTTP (`api.py`)
- **SQLAlchemy 2** — ORM, portable entre SQLite / PostgreSQL / SQL Server
- **requests**, **feedparser**, **trafilatura**, **beautifulsoup4**, **lxml** — scraping y extracción de artículos
- **spaCy** (`es_core_news_lg`) — NER en español (figuras públicas y empresas)
- **pysentimiento** (BETO/RoBERTuito) — análisis de sentimiento en español
- **google-genai** (opcional, de pago) — `GeminiAnalyzer` como motor de análisis alternativo

**Frontend**
- **React 19** + **TypeScript** + **Vite**
- **Tailwind CSS 4**
- **@base-ui/react**, **shadcn**, **lucide-react** — componentes e iconos
- **oxlint** — linting

**Base de datos**
- **PostgreSQL 17** (Docker / desarrollo) o **SQLite** (pruebas rápidas locales)
- **SQL Server** soportado vía `pyodbc` (uso cliente)

**Infraestructura**
- **Docker** + **Docker Compose** — servicios `db` (Postgres), `backend` (FastAPI), `frontend` (Nginx sirviendo el build de Vite), `scraper` (CLI, perfil `tools`)
- **Nginx** — sirve el frontend en producción (`frontend/Dockerfile`, `frontend/nginx.conf`)

**Cache de dependencias en Docker**

Los `Dockerfile` (`Dockerfile.backend` y `frontend/Dockerfile`) están ordenados
para que las dependencias solo se vuelvan a descargar cuando realmente
cambiaron:

- `requirements.txt` / `package.json` + `package-lock.json` se copian **antes**
  que el resto del código, así que si solo cambia código (no dependencias),
  Docker reutiliza la capa de instalación tal cual, sin tocar la red.
- Además usan cache de **BuildKit** (`--mount=type=cache`) para el cache de
  `pip` y de `npm`. Esto hace que, incluso cuando sí cambia una dependencia,
  solo se descargue lo nuevo/actualizado — el resto de paquetes se sirve desde
  el cache local (persiste entre builds aunque la capa de Docker se invalide).
- El modelo de spaCy (`es_core_news_lg`, backend) vive en su propia capa,
  separada de `requirements.txt`, para no re-descargarse cada vez que cambian
  las dependencias de Python.
- El caché de Hugging Face (pesos de `pysentimiento`, ~500 MB) se persiste en
  el volumen `hf_cache` de `docker-compose.yml`, así que sobrevive a
  reconstrucciones de la imagen y no se vuelve a descargar en cada `up`.

Docker (≥ 23) y Docker Compose v2 usan BuildKit por defecto, así que esto
funciona sin configuración extra con `docker compose build` / `docker compose up --build`.

> Detalle técnico completo de la dockerización (servicios, Dockerfiles,
> estrategia de cache, volúmenes, comandos, troubleshooting):
> **[docs/docker.md](docs/docker.md)**.

---

## Requerimientos

**Software**
- Python **3.13** para desarrollo local (Docker usa 3.12; no usar 3.14: las librerías de ML aún no tienen soporte estable)
- Node.js 20+ y npm (para `frontend/`)
- Docker + Docker Compose (opcional, para levantar todo el stack)
- PostgreSQL 14+ si no se usa Docker ni SQLite
- (Opcional) `pyodbc` + ODBC Driver 18 para conectar a SQL Server

**Hardware**
- **Disco**: ~2 GB libres — el modelo de sentimiento (~500 MB) y el modelo de spaCy en español se descargan/cachean en la primera corrida
- **RAM**: mínimo 4 GB; se recomiendan 8 GB para correr los modelos locales (spaCy + pysentimiento) con margen cómodo
- **CPU**: no requiere GPU — los modelos locales corren en CPU; una GPU acelera pysentimiento pero no es necesaria
- **Red**: acceso a internet para el scraping y para la descarga inicial de los modelos (y para la API de Gemini si se usa `GeminiAnalyzer`)

---

## Cómo funciona

Odin ejecuta un **pipeline de 5 pasos** encadenados. Le das una orden por
consola y él hace todo el recorrido, de la web a la base de datos:

```mermaid
flowchart LR
    A[1. Descubrir<br/>qué artículos hay] --> B[2. Descargar<br/>el HTML]
    B --> C[3. Extraer<br/>título, autor, cuerpo]
    C --> D[4. Analizar<br/>tema, sentimiento, figuras]
    D --> E[5. Guardar<br/>en la base de datos]
    E --> F[(BD)]
```

Paso a paso, con palabras sencillas:

1. **Descubrir** — Odin pregunta a cada periódico qué publicó hoy.
   Diario Libre lo dice por **RSS** (9 secciones); Listín no tiene RSS, así que
   Odin lee su **sitemap de Google News**. Resultado: una lista de URLs de
   artículos.

2. **Descargar** — baja el HTML de cada URL. Si la red falla, **reintenta** con
   esperas crecientes; y descarga **varios artículos a la vez** (en paralelo)
   para ir más rápido, sin saturar al periódico.

3. **Extraer** — de ese HTML saca los campos limpios (título, autor, fecha,
   sección, cuerpo) con `trafilatura`, que funciona en casi cualquier periódico
   sin tener que programar selectores frágiles.

4. **Analizar** — sobre el título y el cuerpo:
   - detecta el **tema principal** y palabras clave;
   - calcula el **sentimiento global** (positivo / negativo / neutro);
   - encuentra las **figuras públicas y empresas** mencionadas y, para cada una,
     estima si el artículo **habla bien, mal o neutro** de ella.

5. **Guardar** — escribe todo en la base de datos. Si un artículo ya estaba
   guardado (misma URL), lo **omite** para no repetir trabajo.

Después puedes **consultar** lo guardado con `report.py`.

> ¿Quieres el detalle técnico de cada paso, con diagramas de flujo, la máquina de
> reintentos, el modelo de datos y el diagrama de secuencia completo? Está en
> **[docs/PROCESOS.md](docs/PROCESOS.md)**.

### Qué se guarda (ejemplo)

Para un artículo sobre un incendio, Odin guardaría algo así:

**Artículo**
| campo | valor |
|---|---|
| fuente | `diario_libre` |
| autor | Ana Carolina Cueva |
| título | Bomberos combaten incendio en sucursal de L&R |
| tema principal | incendio |
| sentimiento global | `NEU` |

**Entidades mencionadas** (tabla aparte, ligada al artículo)
| nombre | tipo | opinión |
|---|---|---|
| Cuerpo de Bomberos | ORG | `NEU` |
| Policía Nacional | ORG | `NEU` |
| Roberto Santos Méndez | PERSON | `NEU` |

---

## El análisis es intercambiable

Todo el análisis (paso 4) está detrás de una **interfaz** `Analyzer`. El resto
del programa no sabe cuál se usa, así que puedes cambiar el motor sin tocar nada
más:

- **`LocalAnalyzer`** (por defecto, **gratis**): spaCy + pysentimiento en local.
- **`GeminiAnalyzer`** (opcional, **de pago**): la **API de Google Gemini**,
  mucho más precisa para "¿hablan bien o mal de esta figura?".

```python
from analysis.gemini_analyzer import GeminiAnalyzer
from pipeline import run
run(analyzer=GeminiAnalyzer())   # requiere: pip install google-genai + GEMINI_API_KEY
```

---

## Estructura del código

```
main.py              punto de entrada (CLI)
pipeline.py          orquesta: descubrir -> descargar -> analizar -> guardar
config.py            configuración por variables de entorno (.env)
scrapers/
  base.py            lógica común: descarga (reintentos/concurrencia) + extracción
  diario_libre.py    feeds RSS por sección
  listin.py          sitemap de Google News (Listín no tiene RSS)
analysis/
  base.py            interfaz Analyzer  <-- pieza intercambiable
  local_analyzer.py  spaCy (NER) + pysentimiento (sentimiento) — por defecto, gratis
  gemini_analyzer.py Google Gemini (opcional, de pago)
db/
  models.py          tablas: Article, Entity (SQLAlchemy)
  session.py         conexión (SQLite / PostgreSQL / SQL Server)
report.py            consultas rápidas de resultados
docs/PROCESOS.md     documentación técnica de cada proceso
docs/docker.md        cómo funciona la dockerización (servicios, cache, comandos)
```

---

## Instalación

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download es_core_news_lg
cp .env.example .env        # ajusta DATABASE_URL
```

> Usa **Python 3.13** (no 3.14: las librerías de ML aún no tienen soporte estable).
> La primera corrida descarga los pesos del modelo de sentimiento (~500 MB).

---

## Base de datos

Odin usa SQLAlchemy, así que el mismo código funciona en varios motores; solo
cambias `DATABASE_URL` en `.env`.

**Prueba rápida sin instalar nada (SQLite):**
```bash
DATABASE_URL="sqlite:///odin.db" python main.py --limit 5
```

**PostgreSQL (desarrollo):**
```
DATABASE_URL=postgresql+psycopg2://odin:odin@localhost:5432/odin
```
```bash
createdb odin    # una vez
```

**SQL Server (cliente):** instala `pyodbc` + *ODBC Driver 18* y usa:
```
DATABASE_URL=mssql+pyodbc://usuario:clave@servidor:1433/odin?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes
```
El modelo de datos es portable: **no hay que reescribir código**, solo esta línea.

---

## Uso

> Guía completa paso a paso (instalación, BD, comandos, problemas comunes):
> **[docs/GUIA_DE_USO.md](docs/GUIA_DE_USO.md)**.

```bash
python main.py --list-sources          # ver fuentes disponibles
python main.py --init-db               # crear las tablas
python main.py                         # rastrear ambos periódicos
python main.py --source diario_libre   # solo uno
python main.py --limit 10              # máx. 10 artículos por fuente
```

Revisar resultados:
```bash
python report.py                       # resumen general
python report.py --entity "Abinader"   # opiniones hacia una figura/empresa
```

---

## Notas sobre precisión

| Campo | Calidad con modelos locales (gratis) |
|---|---|
| Autor, título, fecha, sección, cuerpo | Excelente |
| Tema / palabras clave | Buena |
| Sentimiento global | Buena (~75-85%) |
| Figuras y empresas | Buena (~80%) |
| **Opinión hacia una figura concreta** | **Aproximada (~60-70%)** |

`sentiment_toward` se calcula con el sentimiento de las frases donde aparece la
entidad. Es el punto más difícil solo con código; para máxima precisión, usar
`GeminiAnalyzer` (Google Gemini) en vez de `LocalAnalyzer` — misma interfaz.

---

## Cortesía / legalidad

- Se respeta un retardo entre peticiones (`REQUEST_DELAY`) y se envía un
  `User-Agent` identificable.
- Se rastrean feeds/sitemaps públicos. Revisa los términos de uso de cada sitio
  antes de un despliegue a gran escala.
