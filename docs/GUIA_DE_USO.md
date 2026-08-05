# Guía de uso de Odin

Guía práctica, paso a paso, para instalar y usar Odin. Para entender *cómo
funciona por dentro*, ver el [README](../README.md) y
[docs/PROCESOS.md](PROCESOS.md).

---

## 1. Requisitos

- **Python 3.13** (no 3.14 — las librerías de ML aún no lo soportan bien).
- ~4 GB de disco libre y 4 GB de RAM (los modelos locales corren en CPU, sin GPU).
- Internet (para instalar y para descargar los artículos).

Comprueba tu Python:
```bash
python3.13 --version
```

---

## 2. Instalación (una sola vez)

Desde la carpeta del proyecto (`/Users/jazar/Documents/Projects/Odin`):

**macOS / Linux:**
```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download es_core_news_lg
cp .env.example .env
```

**Windows (PowerShell):**
```powershell
python3.13 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m spacy download es_core_news_lg
Copy-Item .env.example .env
```

> La primera vez se descargan ~1.5 GB (torch + modelos). La descarga de los pesos
> del modelo de sentimiento (~416 MB) ocurre sola en la primera corrida.

**Cada vez que abras una terminal nueva**, activa el entorno antes de usar Odin:
```bash
# macOS/Linux
cd /Users/jazar/Documents/Projects/Odin
source .venv/bin/activate

# Windows (PowerShell)
cd C:\ruta\a\Odin
.venv\Scripts\Activate.ps1
```

---

## 3. Elegir la base de datos

Odin guarda donde diga `DATABASE_URL` en tu archivo `.env`. Elige una opción:

### Opción A — SQLite (lo más fácil para probar)
No instala nada. En `.env`:
```
DATABASE_URL=sqlite:///odin.db
```
Se crea el archivo `odin.db` en la carpeta del proyecto.

### Opción B — PostgreSQL
1. Instala y arranca PostgreSQL.
2. Crea la base de datos:
   ```bash
   createdb odin
   ```
3. En `.env`:
   ```
   DATABASE_URL=postgresql+psycopg2://odin:odin@localhost:5432/odin
   ```
   (ajusta usuario/clave a los tuyos).

### Opción C — SQL Server
Instala `pyodbc` y el *ODBC Driver 18*, y en `.env`:
```
DATABASE_URL=mssql+pyodbc://usuario:clave@servidor:1433/odin?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes
```

> Cambiar de motor es **solo cambiar esta línea**; no se toca código.

---

## 4. Primer uso

```bash
# 1. Crear las tablas (una vez por base de datos)
python main.py --init-db

# 2. Rastrear los periódicos (empieza con pocos artículos)
python main.py --limit 5

# 3. Ver un resumen de lo guardado
python report.py
```

Si todo va bien, verás un resumen como:
```
=== Resumen ===
  diario_libre    : 5 artículos nuevos
  listin_diario   : 5 artículos nuevos
  TOTAL           : 10
```

---

## 5. Comandos disponibles

```bash
python main.py --list-sources          # ver los periódicos disponibles
python main.py --init-db               # crear las tablas y salir
python main.py                         # rastrear TODOS los periódicos
python main.py --source diario_libre   # rastrear solo uno
python main.py --source listin_diario --source diario_libre   # varios
python main.py --limit 10              # máximo 10 artículos por periódico
python main.py --analyzer local        # motor de análisis local (por defecto)
python main.py --analyzer gemini       # motor Google Gemini (ver sección 7)
```

Se pueden combinar, p.ej.:
```bash
python main.py --source diario_libre --limit 20
```

> **Sin duplicados:** si vuelves a correrlo, Odin **omite** los artículos que ya
> tenga guardados (compara por URL) y solo añade los nuevos.

---

## 6. Ver los resultados

### Con `report.py` (rápido, en consola)
```bash
python report.py                       # resumen: fuentes, sentimiento, más mencionados
python report.py --entity "Abinader"   # todas las menciones de una figura/empresa
```

### Con un cliente de base de datos (TablePlus, DBeaver…)
- **SQLite:** crea una conexión tipo *SQLite* apuntando al archivo `odin.db`.
- **PostgreSQL / SQL Server:** crea una conexión de ese tipo con host, puerto,
  usuario y clave.

Verás dos tablas:
- **`articles`** — un artículo por fila (autor, título, fecha, tema, sentimiento…).
- **`entities`** — figuras/empresas mencionadas y la opinión hacia cada una,
  ligadas a su artículo por `article_id`.

---

## 7. Cambiar el motor de análisis

Por defecto Odin usa el analizador **local** (gratis). Para usar **Google
Gemini** (más preciso en "¿hablan bien o mal de esta figura?"):

```bash
# macOS/Linux
pip install google-genai
export GEMINI_API_KEY=tu_clave_aqui
python main.py --limit 10 --analyzer gemini

# Windows (PowerShell)
pip install google-genai
$env:GEMINI_API_KEY="tu_clave_aqui"
python main.py --limit 10 --analyzer gemini
```

Puedes correr los dos sobre los mismos periódicos y comparar:
```bash
python main.py --limit 10 --analyzer local
python main.py --limit 10 --analyzer gemini
```

---

## 8. Corridas periódicas (opcional)

Para actualizar la base de datos automáticamente (p.ej. cada mañana), agrega una
tarea que active el entorno y corra Odin.

**macOS/Linux (`cron`)** — ejemplo, todos los días 7am:
```cron
0 7 * * * cd /Users/jazar/Documents/Projects/Odin && ./.venv/bin/python main.py >> odin.log 2>&1
```

**Windows (Programador de tareas)**: crea una tarea básica con
"Iniciar un programa" apuntando a `.venv\Scripts\python.exe`, argumentos
`main.py`, y "Iniciar en" la carpeta del proyecto — desde el Programador de
tareas (`taskschd.msc`) o con `schtasks /create`.

---

## 9. Problemas comunes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `Falta el modelo de spaCy 'es_core_news_lg'` | No se descargó el modelo | `python -m spacy download es_core_news_lg` |
| `No se pudo inicializar la BD (postgresql...)` | Postgres no está corriendo o mal configurado | Arranca Postgres, revisa `DATABASE_URL`, o usa SQLite para probar |
| `ModuleNotFoundError: No module named 'google'` | Falta la librería de Gemini | `pip install google-genai` (solo si usas `--analyzer gemini`) |
| La primera corrida tarda mucho | Está descargando los pesos del modelo (~416 MB) | Es normal solo la primera vez; luego quedan en caché |
| No aparecen artículos nuevos | Ya estaban guardados (dedup por URL) | Normal; borra la BD o espera a que los periódicos publiquen más |
| `python: command not found` o versión 3.14 | Entorno no activado o Python equivocado | `source .venv/bin/activate` (macOS/Linux) o `.venv\Scripts\Activate.ps1` (Windows) — creado con `python3.13` |

---

## 10. Ajustes finos (opcional)

En `.env` puedes ajustar el comportamiento (ver [.env.example](../.env.example)):

| Variable | Por defecto | Qué hace |
|---|---|---|
| `MAX_ARTICLES_PER_SOURCE` | 25 | Tope de artículos por periódico si no usas `--limit` |
| `REQUEST_DELAY` | 1.5 | Segundos base de espera entre reintentos |
| `FETCH_WORKERS` | 4 | Descargas simultáneas por periódico |
| `FETCH_RETRIES` | 3 | Reintentos ante error de red |
| `USER_AGENT` | OdinNewsBot/1.0 | Cómo se identifica ante los periódicos |
