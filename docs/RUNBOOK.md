# Runbook operativo

> Para arquitectura y componentes ver [ARQUITECTURA.md](ARQUITECTURA.md). Este
> documento asume que ya conoces el sistema y necesitas **actuar rápido**
> ante un problema concreto. Escrito para alguien de guardia a las 3 AM que no
> escribió el código.

## Índice rápido

- [Health check](#health-check)
- [Variables de entorno relevantes](#variables-de-entorno-relevantes)
- [Una fuente deja de responder / falla el scraping](#una-fuente-deja-de-responder--falla-el-scraping)
- [Reintentar una corrida fallida](#reintentar-una-corrida-fallida)
- [Cancelar una corrida en curso](#cancelar-una-corrida-en-curso)
- [Rotar la llave de Gemini / Groq](#rotar-la-llave-de-gemini--groq)
- [Migraciones de base de datos](#migraciones-de-base-de-datos)
- [Restaurar un backup](#restaurar-un-backup)
- [Logs y correlation-id](#logs-y-correlation-id)
- [Métricas](#métricas)
- [A quién escalar](#a-quién-escalar)

## Health check

```
GET /api/health
```

Ejecuta `SELECT 1` real contra la BD. `200` si todo bien, `503` si la BD no
responde (`api/routers/misc.py`). Es el endpoint que usa el `HEALTHCHECK` de
Docker (`docker-compose.yml`) — si el contenedor `backend` aparece
`unhealthy`, empieza por aquí: probablemente la BD no está arriba o las
credenciales de `DATABASE_URL` son incorrectas.

## Variables de entorno relevantes

Definidas en [`config.py`](../config.py). Las que más importan en operación:

| Variable | Default | Qué hace |
|---|---|---|
| `DATABASE_URL` | sqlite local / postgres en compose | conexión a la BD |
| `ODIN_ANALYZER` | `local` | motor activo (`local`\|`gemini`\|`groq`\|`hybrid`); inválido = falla el arranque |
| `ODIN_GEMINI_ARBITER` | `false` | arbitraje extra de personas ambiguas — **facturable**, opt-in aparte |
| `ODIN_ALLOWED_DOMAINS` | 9 dominios (uno por medio) | allowlist anti-SSRF de `POST /api/analyze` |
| `ODIN_MAX_DOWNLOAD_BYTES` | 5 MB | corta la descarga de artículos por tamaño |
| `ODIN_CORS_ORIGINS` | — | orígenes permitidos del frontend |
| `ODIN_JWT_SECRET` | efímero si no se define | **si no se define, cada reinicio invalida todas las sesiones activas** |
| `ODIN_LOG_FORMAT` / `ODIN_LOG_LEVEL` | `console`/`INFO` | usar `json` en prod para que el agregador de logs lo parsee |
| `ODIN_SENTRY_DSN` | vacío (apagado) | definir para reportar excepciones a Sentry |
| `ODIN_RESPECT_ROBOTS_TXT` | `true` | **no desactivar en producción**, solo para pruebas locales puntuales |
| `MAX_ARTICLES_PER_SOURCE`, `FETCH_WORKERS`, `FETCH_RETRIES`, `REQUEST_DELAY` | 25 / 4 / 3 / 1.5s | tuning del scraper masivo |

> **Nunca ejecutes pruebas o llamadas reales contra `--analyzer gemini` /
> `ODIN_ANALYZER=gemini` sin que el usuario lo pida** — cada llamada consume
> cuota de pago (ver `CLAUDE.md`).

## Una fuente deja de responder / falla el scraping

1. Confirma si es la fuente o la red: `python main.py --source <fuente>
   --limit 1 --analyzer local` desde una shell con acceso a la BD.
2. Revisa el `crawl_run` más reciente para esa fuente:
   `GET /api/crawl-runs` (o consulta directa a la tabla `crawl_runs`) —
   `stats_by_source` trae el desglose. Si `articles_failed` es alto para una
   sola fuente, sospecha de un cambio de sitemap/RSS en el medio.
3. **No hay `fetch_log` por URL** (gap conocido, `task.md` §2.3): no puedes
   ver qué URL individual falló, solo el agregado por corrida. Si necesitas
   diagnóstico fino, corre esa fuente sola con `--limit` bajo y logs en nivel
   `DEBUG` y revisa la salida de consola.
4. Si el medio cambió su sitemap/RSS: actualizar `feeds`/`sitemaps` en
   `scrapers/do_scrapers.py` para esa clase. Si el medio migró a un formato
   sin sitemap fiable, replicar el patrón de excepción de Acento (regex sobre
   la portada) — ver [ADR-001](adr/0001-trafilatura-y-sitemaps-sobre-selectores.md).
5. Si trafilatura deja de extraer contenido de un medio (título/cuerpo
   vacíos pero fetch OK): probar con una versión más nueva de `trafilatura`
   antes de escribir un extractor a medida.

## Reintentar una corrida fallida

**No existe endpoint de "retry"** para `analyze_jobs` ni `scrape_jobs`. La
forma de reintentar es crear un job nuevo:

- Análisis puntual (`analyze_jobs`): volver a `POST /api/analyze` con la
  misma URL. Si el artículo ya se guardó, el endpoint responde `200` directo
  sin re-analizar (no reprocesa artículos ya persistidos).
- Corrida masiva (`scrape_jobs`): `POST /api/scrape-jobs` de nuevo. Bloqueado
  con `409` mientras haya un job `pending`/`running` — confirma primero que
  el anterior terminó (`GET /api/scrape-jobs/{id}`) o cancélalo (siguiente
  sección).

## Cancelar una corrida en curso

```
POST /api/scrape-jobs/{id}/cancel
```

Cancelación **cooperativa**: marca `cancel_requested=true`; el pipeline lo
revisa entre fuentes y entre artículos (`pipeline.py`), no corta a mitad de
una petición HTTP en curso. Espera a que el job pase a `status=cancelled`
(polling a `GET /api/scrape-jobs/{id}`) antes de asumir que terminó.

## Rotar la llave de Gemini / Groq

1. Generar la nueva llave en la consola del proveedor (Google AI Studio /
   Groq).
2. Actualizar `GEMINI_API_KEY` (o `GROQ_API_KEY`) en el `.env` del entorno
   correspondiente — **nunca** commitear la llave.
3. Reiniciar el contenedor/proceso `backend` (la config se congela al
   importar el módulo, `task.md` §3.5 — no hay recarga en caliente).
4. Confirmar en el log de arranque qué motor está activo y que no quedó en
   modo facturado por accidente: `ODIN_ANALYZER` sigue mandando, la llave por
   sí sola no cambia el motor (ver [ADR-005](adr/0005-seleccion-explicita-de-analizador.md)).
5. Revocar la llave vieja en la consola del proveedor una vez confirmado que
   el sistema arrancó bien con la nueva.

## Migraciones de base de datos

```bash
# ver el estado actual de una BD
alembic current

# aplicar migraciones pendientes
alembic upgrade head

# generar una nueva migración tras cambiar db/models.py
alembic revision --autogenerate -m "descripcion_corta"
# revisar el archivo generado en alembic/versions/ antes de aplicar
alembic upgrade head

# revertir la última migración
alembic downgrade -1
```

`db/session.py::init_db()` **solo** crea tablas que no existen
(`create_all`), nunca altera columnas de tablas existentes — todo cambio de
esquema real pasa por Alembic (ver [ADR-002](adr/0002-alembic-sobre-migraciones-caseras.md)).
Nunca ejecutar `alembic upgrade head` en producción sin haber revisado antes
el archivo de migración autogenerado.

## Restaurar un backup

**No existe ningún script de backup/restore en el repo** (`scripts/` no
tiene `backup.py`/`restore.py`) — gap operativo real, señalarlo antes de ir
a producción con datos de cliente. Hoy la única persistencia es el volumen
Docker `pgdata` de PostgreSQL. Mientras no exista tooling propio:

```bash
# backup manual (fuera de este repo, ejecutar contra el contenedor db)
docker compose exec db pg_dump -U <user> <db> > backup_$(date +%Y%m%d).sql

# restore manual
docker compose exec -T db psql -U <user> <db> < backup_YYYYMMDD.sql
```

Antes de restaurar sobre una BD con datos nuevos, confirma con quien pidió el
restore que está bien perder lo escrito después del backup.

## Logs y correlation-id

Cada request HTTP y cada corrida masiva tiene un `correlation_id` (header de
respuesta `X-Correlation-ID`; también guardado en `crawl_runs.correlation_id`
/ `scrape_jobs.correlation_id`). Para investigar un incidente puntual, filtra
los logs por ese id — conecta la petición del usuario con la corrida de
scraping/análisis que disparó.

`ODIN_LOG_FORMAT=json` en producción para que el agregador de logs (si
existe) pueda parsear estructuradamente; `console` es más legible en dev.

## Métricas

```
GET /metrics
```

Prometheus. Claves a vigilar:
- `odin_http_requests_total` / `odin_http_request_duration_seconds` — salud
  general de la API.
- `odin_pipeline_runs_total`, `odin_pipeline_articles_total`,
  `odin_pipeline_run_duration_seconds` — salud del scraping masivo.
- `odin_gemini_requests_total`, `odin_gemini_tokens_total` — **vigilar de
  cerca si `ODIN_ANALYZER=gemini` o el árbitro está activo**: es gasto real.
- `odin_crawl_run_in_progress` — debería ser 0 o 1 (solo un scrape_job activo
  a la vez); si queda en 1 sin corrida real, hay un job atascado —
  investigar antes de forzar nada en la BD a mano.

## A quién escalar

Este runbook no tiene todavía una matriz de escalamiento (equipo de una
persona a la fecha de escritura). Mínimo viable antes de operar con un
cliente real: definir quién recibe alertas de Sentry, quién tiene acceso a
rotar credenciales de Gemini/Groq/JWT, y quién autoriza un restore de backup.
