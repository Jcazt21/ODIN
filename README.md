# Odin — Análisis de artículos de prensa dominicana, a demanda

Odin analiza artículos de prensa dominicana **uno a uno y a petición tuya**: le
pegas la URL de un artículo, él lo descarga y lo analiza, tú revisas el
resultado y decides si se guarda en la base de datos.

- **Autor**, **título**, **fecha**, **sección**, **cuerpo**, **URL**, **fuente**
- **De qué se habla**: tema principal + palabras clave
- **Sentimiento global**: `POS` / `NEG` / `NEU` (bueno / malo / neutro)
- **Figuras públicas y empresas** mencionadas
- **Opinión hacia cada figura/empresa**: si hablan bien, mal o neutro de ella

> **No hay nada automático.** Odin no sale a buscar noticias por su cuenta, no
> corre solo y no consulta feeds ni sitemaps en el flujo normal: procesa
> únicamente las URLs que tú le pegas. Existe además un rastreo masivo por
> consola, **opcional y de ejecución manual** — ver
> [Rastreo masivo](#rastreo-masivo-opcional-y-manual).

El análisis usa por defecto **modelos locales gratis** (spaCy + pysentimiento en
español), sin API de pago.

---

## Stack tecnológico

**Backend**
- **Python 3.13** — en Docker (`Dockerfile.backend`) y recomendado en local (ver [Instalación](#instalación))
- **FastAPI** + **Uvicorn** — API HTTP: paquete `api/` (routers en `api/routers/`, schemas en `api/schemas.py`) con la lógica de negocio en `services/`
- **SQLAlchemy 2** + **Alembic** — ORM y migraciones versionadas, portable entre SQLite / PostgreSQL / SQL Server
- **requests**, **feedparser**, **trafilatura**, **beautifulsoup4**, **lxml** — scraping y extracción de artículos
- **spaCy** (`es_core_news_lg`) — NER en español (figuras públicas y empresas)
- **pysentimiento** (BETO/RoBERTuito) — análisis de sentimiento en español
- **google-genai** (opcional, de pago) — `GeminiAnalyzer`
- **groq** (opcional, gratis con límites) — `GroqAnalyzer`/`HybridAnalyzer`; en modo `groq+gemini` corre primero y cae a Gemini como red de seguridad si falla
- **structlog** + **prometheus-client** + Sentry (opcional) — logging estructurado, métricas en `/metrics`, reporte de errores

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

El flujo normal —y el único que hace falta— arranca **siempre contigo pegando
una URL**. Odin nunca decide por su cuenta qué analizar:

```mermaid
flowchart LR
    A[1. Pegas la URL<br/>del artículo] --> B[2. Descargar<br/>el HTML]
    B --> C[3. Extraer<br/>título, autor, cuerpo]
    C --> D[4. Analizar<br/>tema, sentimiento, figuras]
    D --> E[5. Revisas<br/>y corriges]
    E --> F[6. Guardar<br/>si te convence]
    F --> G[(BD)]
```

Paso a paso, con palabras sencillas:

1. **Pegas la URL** — en la pestaña **Analizar** del frontend. Por debajo es un
   `POST /api/analyze` con esa dirección y nada más: no se consulta ningún feed,
   ningún sitemap, ni se pregunta qué publicó el periódico hoy.

2. **Descargar** — baja el HTML de esa única URL. Si la red falla, **reintenta**
   con esperas crecientes.

3. **Extraer** — de ese HTML saca los campos limpios (título, autor, fecha,
   sección, cuerpo) con `trafilatura`, que funciona en casi cualquier periódico
   sin tener que programar selectores frágiles.

4. **Analizar** — sobre el título y el cuerpo:
   - detecta el **tema principal** y palabras clave;
   - calcula el **sentimiento global** (positivo / negativo / neutro);
   - encuentra las **figuras públicas y empresas** mencionadas y, para cada una,
     estima si el artículo **habla bien, mal o neutro** de ella.

5. **Revisas** — el resultado se te muestra antes de tocar la base de datos.
   Puedes corregir entidades y sentimientos.

6. **Guardar** — solo si lo pides (`POST /api/articles`). Si esa URL ya estaba
   guardada, no se duplica.

Después puedes **consultar** lo guardado con `report.py` o en la pestaña
**Reportes**.

### Rastreo masivo (opcional y manual)

Odin también trae un rastreador de lotes, **que no se usa en el alcance actual**
y **nunca corre solo**: no hay cron, no hay scheduler, y el servicio `scraper` de
`docker-compose.yml` está detrás del perfil `tools`, así que `docker compose up`
no lo arranca. Solo se ejecuta si tú escribes `odin` a mano.

Cuando se ejecuta, antepone un paso de **descubrimiento**: le pregunta a cada
periódico qué publicó hoy —Diario Libre por **RSS**, Listín por su **sitemap de
Google News**— y de ahí saca una lista de URLs que luego pasa por los mismos
pasos 2-4, guardando sin revisión humana.

> Está documentado porque el código existe, no porque haga falta usarlo. Si en
> algún momento quieres monitoreo continuo en vez de análisis a demanda, este es
> el punto de partida.

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

Todo el análisis (paso 4) está detrás de una **interfaz** `Analyzer`
(`analysis/base.py`). El resto del programa no sabe cuál se usa, así que puedes
cambiar el motor sin tocar nada más. Hay cinco:

| Motor | Costo | Qué hace |
|---|---|---|
| `local` *(por defecto)* | **Gratis** | `LocalAnalyzer`: spaCy + pysentimiento en local. No calcula los campos de encuadre (framing, capas de sentimiento) — exigen comprensión del texto, no extracción de patrones. |
| `gemini` | **De pago** | `GeminiAnalyzer`: API de Google Gemini (`gemini-3.5-flash`). Una llamada por artículo; mucho más precisa para "¿hablan bien o mal de esta figura?" y produce todos los campos de encuadre. |
| `groq` | Gratis, con límites | `GroqAnalyzer`: mismo esquema que Gemini vía la API de Groq (`openai/gpt-oss-120b`), free tier con rate limit propio (TPM). |
| `hybrid` | Gratis, con límites | `HybridAnalyzer`: tema/palabras clave/sentimiento global con `LocalAnalyzer` (gratis) + entidades y encuadre con Groq en la misma llamada — NER pura con patrones se rompe con nombres compuestos y homónimos, así que esa parte sí pasa por el LLM. |
| `groq+gemini` | Gratis, con excepción facturada | `GroqWithGeminiFallback`: intenta con Groq primero; si falla (rate limit, JSON truncado, error de red) reintenta con Gemini. El linaje guardado (`analyzer_name`) dice cuál de los dos respondió realmente. |

### Cuál se usa, y por qué nunca por accidente

El motor se elige **siempre de forma explícita** vía `ODIN_ANALYZER`. Tener
`GEMINI_API_KEY`/`GROQ_API_KEY` en el `.env` **no** activa un modo de pago o
con límites: la llave puede estar ahí para el CLI, para el árbitro puntual, o
simplemente olvidada. Una credencial no debe ser un interruptor de gasto.

| Variable | Valor | Qué hace |
|---|---|---|
| `ODIN_ANALYZER` | `local` *(por defecto)* | Ver tabla de arriba. **Gratis.** |
| `ODIN_ANALYZER` | `gemini` \| `groq` \| `hybrid` \| `groq+gemini` | Ver tabla de arriba. |
| `ODIN_GEMINI_ARBITER` | `0` *(por defecto)* | Sin llamadas extra. |
| `ODIN_GEMINI_ARBITER` | `1` | Llamada **facturada** adicional a Gemini para desambiguar personas dudosas. Se salta si el motor principal ya es `gemini` (ya excluye lugares/homenajes en su propio prompt) y solo se llama desde `/api/analyze`, nunca desde el rastreo masivo. |

Un valor inválido (`ODIN_ANALYZER=gemeni`) **falla al arrancar** en vez de caer
en un default silencioso. Y al iniciar, la API escribe en el log qué motor está
usando, con aviso explícito si puede facturar.

En la consola es el mismo criterio, con `--analyzer`:

```bash
odin                                 # local, gratis (por defecto)
odin --analyzer gemini               # de pago, explícito
odin --analyzer groq                 # gratis, con límites
odin --analyzer hybrid               # gratis, con límites
```

> El rastreo masivo (`main.py`, `POST /api/scrape-jobs`) restringe el motor a
> `local`/`groq`/`hybrid` — `gemini` y `groq+gemini` no son valores aceptados
> ahí, a propósito: una corrida de varios cientos de artículos con un motor
> facturado sin querer sería un gasto grande por accidente.

---

## Estructura del código

```
api/                 API HTTP (FastAPI) — el camino principal: analizar / guardar / listar
  __init__.py        app, middleware (CORS, correlation-id, métricas), monta los routers
  schemas.py         requests/respuestas Pydantic (fuente de los tipos TS del frontend)
  deps.py            dependencias compartidas (sesión de BD)
  routers/           un módulo por grupo de rutas: analyze, articles, entities, aliases,
                     canonical_entities, scrape_jobs, misc (health/metrics)
services/            lógica de negocio (SQLAlchemy) detrás de cada router — los routers
                     no hablan a la BD directo
  analyzer_registry.py  instancia única del Analyzer activo del proceso
auth.py              login de usuario único + JWT
frontend/            React + Vite + React Query — páginas Analizar / Reportes / Entidades
                     / Siglas / Scraper, rutas reales con react-router-dom
config.py            configuración por variables de entorno (.env)
scrapers/
  base.py            descarga (reintentos, throttle por dominio, robots.txt) + extracción
  do_scrapers.py     7 de las 9 fuentes dominicanas (descubrimiento por RSS/sitemap)
  diario_libre.py, listin.py   las otras 2
analysis/
  base.py            interfaz Analyzer + AnalysisResult  <-- pieza intercambiable
  local_analyzer.py  spaCy (NER) + pysentimiento (sentimiento) — por defecto, gratis
  gemini_analyzer.py Google Gemini (opcional, de pago)
  groq_analyzer.py   Groq: GroqAnalyzer + HybridAnalyzer (opcional, gratis con límites)
  fallback_analyzer.py  GroqWithGeminiFallback: Groq primero, Gemini como red de seguridad
  canonicalize.py    unificación de nombres de entidades
  entity_arbiter.py  desambiguación puntual (solo flujo manual)
db/
  models.py          7 tablas — ver docs/DATA_DICTIONARY.md
  session.py         conexión (SQLite / PostgreSQL / SQL Server)
  canonical_entities.py, aliases.py   dimensión de entidad y resolución de siglas
alembic/             migraciones versionadas del esquema
report.py            consultas rápidas de resultados
scripts/             utilidades sueltas (hash de contraseña, fusión de entidades, eval)
url_guard.py         anti-SSRF: allowlist + bloqueo de IP privada (único punto de red hacia URLs de usuario)
observability.py     logging estructurado, correlation-id, métricas Prometheus, Sentry opt-in

--- rastreo masivo, opcional y manual ---
main.py              punto de entrada (CLI)
pipeline.py          orquesta: descubrir -> descargar -> analizar -> guardar
scrape_jobs.py        puente API↔pipeline.run() para corridas encoladas desde el frontend

docs/
  ARQUITECTURA.md    vista C4 (contexto, contenedores, componentes)
  PROCESOS.md        cada proceso del pipeline paso a paso, con diagramas
  DATA_DICTIONARY.md  cada columna de cada tabla: significado, quién la produce
  RUNBOOK.md          operación: fuente caída, jobs, migraciones, backups
  LEGAL.md             ToS por medio, datos personales, retención
  PRECISION.md          metodología de evaluación y estado del golden set
  GUIA_DE_USO.md         guía paso a paso para el usuario final
  docker.md               cómo funciona la dockerización (servicios, cache, comandos)
  adr/                     decisiones arquitectónicas (por qué se eligió cada cosa)
```

---

## Instalación

**macOS / Linux:**
```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download es_core_news_lg
cp .env.example .env        # ajusta DATABASE_URL
```

**Windows (PowerShell):**
```powershell
python3.13 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m spacy download es_core_news_lg
Copy-Item .env.example .env    # ajusta DATABASE_URL
```

> Usa **Python 3.13** (no 3.14: las librerías de ML aún no tienen soporte estable).
> La primera corrida descarga los pesos del modelo de sentimiento (~500 MB).

---

## Base de datos

Odin usa SQLAlchemy, así que el mismo código funciona en varios motores; solo
cambias `DATABASE_URL` en `.env`.

**Prueba rápida sin instalar nada (SQLite):**
```bash
# macOS/Linux
DATABASE_URL="sqlite:///odin.db" odin --limit 5

# Windows (PowerShell)
$env:DATABASE_URL="sqlite:///odin.db"; odin --limit 5
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

**Uso normal**: levantas el backend y el frontend, entras a la interfaz, y en la
pestaña **Analizar** pegas la URL del artículo. Todo el flujo vive ahí.

```bash
odin --init-db                         # crear las tablas (una vez)
uvicorn odin.api:app --reload          # backend
cd frontend && npm run dev             # frontend
```

Revisar resultados:
```bash
python -m odin.core.report             # resumen general
python -m odin.core.report --entity "Abinader"   # opiniones hacia una figura/empresa
```

**Rastreo masivo** (opcional, manual, fuera del alcance actual — ver
[Rastreo masivo](#rastreo-masivo-opcional-y-manual)):
```bash
odin --list-sources                    # ver fuentes disponibles
odin                                   # rastrear todas las fuentes
odin --source diario_libre             # solo una
odin --limit 10                        # máx. 10 artículos por fuente
```

---

## Acceso a la aplicación web

La interfaz pide usuario y contraseña. **No hay registro**: es una herramienta
interna con un único operador, definido por variables de entorno.

```bash
python scripts/hash_password.py    # pide la clave y devuelve la línea del .env
```

En `.env`:

| Variable | Para qué |
|---|---|
| `ODIN_AUTH_USER` | Usuario (por defecto `admin`) |
| `ODIN_AUTH_PASSWORD_HASH` | Hash PBKDF2 que genera el script de arriba |
| `ODIN_AUTH_PASSWORD` | Alternativa en claro, **solo desarrollo** |
| `ODIN_JWT_SECRET` | Firma de los tokens. Sin ella, las sesiones mueren al reiniciar |
| `ODIN_JWT_TTL_HOURS` | Vigencia de la sesión (por defecto 12) |
| `ODIN_CORS_ORIGINS` | Orígenes permitidos, separados por coma |

El login devuelve un JWT que el frontend guarda y manda en `Authorization:
Bearer`. **Exigen token**: `POST /api/analyze`, `POST /api/articles` y todas las
escrituras de siglas (`POST`/`PUT`/`DELETE /api/aliases`). Las lecturas
(`GET /api/articles`, `/api/aliases`, `/api/health`) siguen abiertas.

Si no configuras ninguna contraseña, el login rechaza todo: el sistema queda
cerrado, no abierto.

---

## Desarrollo: lint, tipos y ganchos de commit

```bash
pip install -e ".[dev]"     # ruff, mypy, pre-commit, pytest, uv, pip-audit
pre-commit install          # una vez por clon
```

| Comando | Qué hace |
|---|---|
| `ruff check .` | Lint (errores reales, imports, modernización, trampas comunes) |
| `ruff check . --fix` | Arregla lo que se puede automáticamente |
| `mypy` | Tipos. Configuración en `pyproject.toml`, sin `strict` por ahora |
| `pytest` | Pruebas (`tests/`, SQLite en memoria — ver `tests/conftest.py`) |
| `pip-audit -r requirements.lock` | Vulnerabilidades conocidas en las dependencias fijadas |
| `pre-commit run --all-files` | Lint y tipos sobre el repo completo (no corre pytest ni pip-audit) |

La configuración de las tres herramientas vive en [pyproject.toml](pyproject.toml).
Las dependencias de ejecución siguen declarándose en `requirements.txt`, que
`pyproject.toml` lee — una sola lista, sin copias que se desincronizan.

**CI** ([.github/workflows/ci.yml](.github/workflows/ci.yml)) corre 5 jobs en
cada push y pull request a `main`: `lint` (ruff), `types` (mypy), `test`
(pytest en Linux), `test-windows` (pytest en Windows — el cliente corre Odin
ahí, es la red de seguridad de portabilidad) y `pip-audit`. Los jobs de tipos y
tests instalan desde `requirements.lock` con `--require-hashes` (menos
`test-windows`, que usa `requirements-ci.txt` sin pin de hash porque el lock
está fijado a Linux).

**`ruff format` está apagado a propósito.** Reformatear todo el backend antes de
tener pruebas produce un diff enorme que esconde los cambios reales; se activa
cuando exista la red de seguridad.

### requirements.lock

[requirements.lock](requirements.lock) fija las **117 dependencias transitivas**
con hash, para que dos instalaciones en fechas distintas den el mismo entorno.
Se regenera cuando cambie `requirements.txt`:

```bash
uv pip compile requirements.txt --generate-hashes --python-version 3.13 \
    --python-platform x86_64-unknown-linux-gnu --torch-backend cpu \
    -o requirements.lock
```

- **`--python-platform x86_64-unknown-linux-gnu`**: `Dockerfile.backend` y los
  runners de GitHub Actions son Linux; sin fijar la plataforma, `uv` resuelve
  para el sistema operativo donde se corre el comando (p. ej. faltaría
  `uvloop`, que no soporta Windows, si se regenera desde ahí).
- **`--torch-backend cpu`**: `torch` llega de rebote
  (`pysentimiento` -> `transformers`/`accelerate` -> `torch`). En Linux, el
  índice por defecto de PyPI resuelve a la build con CUDA, que arrastra
  `nvidia-*`/`triton` (~4.5GB) sin que el contenedor tenga GPU. Esta flag fija
  la build `+cpu` (índice de PyTorch) directamente en el lock. Instalar desde
  el lock requiere entonces `--extra-index-url
  https://download.pytorch.org/whl/cpu` (ver `Dockerfile.backend` y
  `.github/workflows/ci.yml`), porque esa build solo vive ahí, no en PyPI.

> `Dockerfile.backend` y el CI de GitHub Actions
> ([.github/workflows/ci.yml](.github/workflows/ci.yml)) instalan desde este
> lock con `pip install --require-hashes`, así que los builds y los checks de
> CI son reproducibles. Ver [docs/docker.md](docs/docker.md#21-backend--scraper--dockerfilebackend).

---

## Documentación

Este README es la puerta de entrada. El detalle técnico vive en `docs/`:

| Documento | Para qué |
|---|---|
| [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) | Vista C4: contexto, contenedores, componentes |
| [docs/PROCESOS.md](docs/PROCESOS.md) | Cada proceso del pipeline paso a paso, con diagramas |
| [docs/DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md) | Cada columna de cada tabla: significado, quién la produce |
| [docs/RUNBOOK.md](docs/RUNBOOK.md) | Operación: fuente caída, reintentar/cancelar jobs, migraciones, backups |
| [docs/LEGAL.md](docs/LEGAL.md) | ToS por medio, datos personales (Ley 172-13/GDPR), retención |
| [docs/PRECISION.md](docs/PRECISION.md) | Metodología de evaluación y estado real del golden set |
| [docs/GUIA_DE_USO.md](docs/GUIA_DE_USO.md) | Guía paso a paso para el usuario final |
| [docs/docker.md](docs/docker.md) | Dockerización: servicios, cache, comandos, troubleshooting |
| [docs/adr/](docs/adr/) | Por qué se eligió cada decisión no obvia (ADRs) |

### Checkpoint de documentación (§10.1 de task.md)

La documentación de Odin ya se desactualizó una vez en silencio (README
describía 2 fuentes cuando había 8; `api.py` seguía citado meses después de
partirse en `api/` + `services/`). El motivo no fue falta de prosa, fue falta
de un punto donde alguien se preguntara "¿esto invalida algún doc?". Antes de
cerrar cualquier cambio que toque uno de estos puntos, actualiza el documento
correspondiente **en el mismo cambio**, no después:

| Si cambias… | Actualiza… |
|---|---|
| `db/models.py` (columna nueva, tabla nueva) | [docs/DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md) |
| `api/schemas.py`, un router, o un servicio nuevo | [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) |
| Un scraper (`scrapers/`) o el conteo de fuentes | Este README (Stack, Estructura, allowlist) + [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) |
| Un analizador (`analysis/`) o `ODIN_ANALYZER` | Este README (El análisis es intercambiable) + [docs/PROCESOS.md](docs/PROCESOS.md) |
| Una decisión no obvia y difícil de revertir | Un [ADR nuevo](docs/adr/) — no un comentario largo en el código |
| Un cambio operativo (variable de entorno, comando, migración) | [docs/RUNBOOK.md](docs/RUNBOOK.md) |
| Algo que toque datos personales o retención | [docs/LEGAL.md](docs/LEGAL.md) |

No hace falta un proceso de PR formal para que esto valga: es un solo dueño
del repo hoy. Para que el checkpoint no dependa solo de acordarse,
[`scripts/check_docs_freshness.py`](scripts/check_docs_freshness.py) corre en
cada commit (`.pre-commit-config.yaml`) y avisa — **sin bloquear** — cuando el
commit toca una de las rutas de la tabla de arriba sin tocar ningún archivo en
`docs/` o este README. No es un gate duro: qué cuenta como "cambio que amerita
doc" es juicio humano (un fix de un typo no necesita ARQUITECTURA.md), así que
el script recuerda en el punto más barato para actuar, no impone.

---

## Qué URLs se pueden analizar

`POST /api/analyze` descarga una URL que escribe el usuario y le devuelve el
contenido. Sin control, eso convierte al servidor en un proxy de lectura hacia
su propia red interna. [url_guard.py](url_guard.py) lo evita con tres capas:

1. **Allowlist de dominios** (`ODIN_ALLOWED_DOMAINS`) — por defecto los 9 medios
   dominicanos que Odin cubre, más sus subdominios. Todo lo demás: `400`.
2. **Bloqueo de destinos internos** — el dominio se resuelve *antes* de conectar
   y se rechaza si alguna de sus IPs es loopback, privada, link-local
   (`169.254.0.0/16`, la metadata de AWS/GCP), CGNAT, multicast o reservada.
   Se revalida en **cada redirección**, que se siguen a mano.
3. **Límites de la respuesta** — máximo 5 MB (`ODIN_MAX_DOWNLOAD_BYTES`), solo
   `Content-Type` de texto/HTML/XML, puertos 80 y 443, URLs de hasta 2048
   caracteres y sin credenciales embebidas.

**Para analizar un medio nuevo hay que agregar su dominio a
`ODIN_ALLOWED_DOMAINS`.** Es a propósito: la allowlist es la defensa fuerte, y
en este producto coincide exactamente con el alcance del negocio.

El rastreo masivo (`main.py`) no pasa por este guard: sus URLs salen de los
sitemaps y feeds de las fuentes ya configuradas en el código, no de un usuario.

---

## Notas sobre precisión

`sentiment_toward` (con `LocalAnalyzer`) se calcula con el sentimiento de las
frases donde aparece la entidad — es el campo más difícil de acertar solo con
código; para máxima precisión, usar un motor LLM (`gemini`/`groq`/`hybrid`) en
vez de `local` — misma interfaz.

**No hay una cifra de precisión publicable todavía.** El golden set etiquetado
a mano (`tests/eval/golden_set.jsonl`) tiene 7 artículos — insuficiente para un
número defendible; ver metodología, estado real y cómo correr la evaluación en
**[docs/PRECISION.md](docs/PRECISION.md)**. No repitas un porcentaje de
precisión frente a un cliente sin haberlo corrido primero sobre una muestra
representativa.

---

## Cortesía / legalidad

- En el flujo normal Odin hace **una petición por artículo que tú pegas**, así
  que la carga sobre el periódico es la misma que si abrieras la página tú.
- Se envía un `User-Agent` identificable (`config.py`).
- El rastreo masivo (`main.py`, `pipeline.py`) respeta un throttle real **por
  dominio**: `REQUEST_DELAY` es el intervalo mínimo entre dos peticiones
  exitosas al mismo host, sin importar cuántos `FETCH_WORKERS` concurrentes
  haya ([scrapers/base.py](scrapers/base.py)).
- También se lee y respeta `robots.txt` de cada dominio (`urllib.robotparser`,
  cacheado por proceso): las rutas que excluye no se piden, y si declara
  `Crawl-delay` se usa ese valor cuando es mayor que `REQUEST_DELAY`.
  Desactivable solo para pruebas locales con `ODIN_RESPECT_ROBOTS_TXT=0`.
- Se guarda el texto íntegro de artículos con copyright, sin política de
  retención todavía. **Revisión de ToS por medio, base legal del tratamiento de
  datos personales (Ley 172-13/GDPR) y checklist antes de entregar a un
  cliente: [docs/LEGAL.md](docs/LEGAL.md)** — la tabla de ToS por medio sigue
  pendiente ahí, no está resuelta por este README.
