# Handoff: Odin — rediseño de UI

## Overview
Rediseño completo de la interfaz de **Odin**, herramienta interna de monitoreo de prensa dominicana (un solo operador; pega una URL, el backend analiza con LLM, el operador corrige y guarda como reporte consultable).

Cubre: sistema de tokens (claro + oscuro), login, workspace con nav tipo pill, pantalla **Analizar**, **Reportes** (tabla densa ordenable + detalle), y versiones rediseñadas de **Entidades canónicas** y **Siglas**. Objetivo: interfaz **seria, directa y legible**, densidad media, color con función semántica, sin sensación de prototipo.

Contratos respetados sin cambios: endpoints, forma de datos y valores de enums (`framing`, `headline_intent`, `lead_orientation`, `source_quality`, `PERSON`/`ORG`, `POS`/`NEG`/`NEU`), flujo de auth (JWT en localStorage, 401 → login), y las 4 áreas funcionales.

## About the Design Files
Los archivos de este bundle son **referencias de diseño hechas en HTML** — prototipos que muestran el look y el comportamiento pretendido, **no código de producción para copiar tal cual**. La tarea es **recrear estos diseños en el entorno existente del repo de Odin**: React 19 + Vite + TypeScript, Tailwind CSS v4, shadcn (`components.json`, style `base-nova`), primitivas `@base-ui/react`, iconos `lucide`. Usa esos patrones y librerías; no introduzcas un framework nuevo ni reescribas el cliente API (`src/lib/odin-api.ts` y `src/lib/api-types.ts` siguen siendo la fuente de verdad, se generan del OpenAPI).

`Odin.dc.html` es un prototipo de una sola página con datos de muestra hardcodeados y un selector superior (Fundamentos / Login / Workspace) que **existe solo para revisar el diseño** — no se implementa en la app real. Necesita `support.js` (incluido) para abrirse en el navegador.

`Plasma.jsx` **sí es código real y reusable** (componente de React Bits adaptado, usa `ogl`): cópialo al repo y ajusta solo los imports.

## Fidelity
**Alta fidelidad (hifi).** Colores, tipografía, espaciado, radios, estados hover/focus y microcopy están definitivos; recréalo con fidelidad usando Tailwind v4 + shadcn. Deliberadamente abierto: el responsive por debajo de 768px (el uso real es escritorio) y los flujos internos de fusión de entidades / edición inline de siglas, que se mantienen funcionalmente como hoy.

---

## Design Tokens

CSS custom properties en un bloque global (en el repo: `src/index.css`, junto a los tokens de shadcn). Tema conmutado con `data-theme="light|dark"` en la raíz. **El acento cambia de familia entre temas** (morado en claro, teal en oscuro — patrón Material).

### Modo claro (default)
| Token | Valor | Uso |
|---|---|---|
| `--bg` | `oklch(0.975 0.003 262)` | fondo de app |
| `--surface` | `#ffffff` | superficie base opaca |
| `--surface-2` | `oklch(0.965 0.005 262)` | inputs, thead, cajas internas |
| `--surface-3` | `oklch(0.945 0.007 262)` | skeletons, hover de superficie |
| `--panel` | `oklch(1 0 0 / 0.8)` | **cards y módulos (translúcidos)** |
| `--panel-strong` | `oklch(1 0 0 / 0.9)` | nav, card de login, diálogos (con blur) |
| `--border` | `oklch(0.905 0.007 262)` | bordes 1px |
| `--border-strong` | `oklch(0.84 0.01 262)` | botón secundario, bordes dashed |
| `--text` | `oklch(0.24 0.016 265)` | texto principal |
| `--muted` | `oklch(0.52 0.014 265)` | texto secundario |
| `--faint` | `oklch(0.65 0.012 265)` | etiquetas, metadatos |
| `--accent` | `#6200EE` | acciones primarias, tab activo |
| `--accent-hover` | `#3700B3` | hover de primario |
| `--accent-fg` | `#ffffff` | texto sobre acento |
| `--accent-soft` | `oklch(0.955 0.028 296)` | fondo de badge de acento |
| `--accent-border` | `oklch(0.86 0.07 296)` | borde de badge de acento |
| `--pos` | `#1B873B` | sentimiento positivo |
| `--pos-soft` | `oklch(0.955 0.035 150)` | fondo positivo |
| `--neg` | `#B00020` | negativo / error / destructivo |
| `--neg-soft` | `oklch(0.955 0.035 20)` | fondo negativo |
| `--neu` | `oklch(0.5 0.012 265)` | neutro |
| `--neu-soft` | `oklch(0.955 0.004 265)` | fondo neutro |
| `--warn` | `oklch(0.52 0.12 75)` | advertencia ("revisar") |
| `--warn-soft` | `oklch(0.96 0.05 85)` | fondo advertencia |
| `--shadow` | `0 1px 2px oklch(0.24 0.02 265 / 0.06), 0 8px 24px -12px oklch(0.24 0.02 265 / 0.14)` | login, diálogo, nav |
| `--shadow-sm` | `0 1px 2px oklch(0.24 0.02 265 / 0.07)` | cards |

### Modo oscuro (`[data-theme="dark"]`)
| Token | Valor |
|---|---|
| `--bg` | `oklch(0.185 0.012 265)` |
| `--surface` | `oklch(0.225 0.013 265)` |
| `--surface-2` | `oklch(0.255 0.014 265)` |
| `--surface-3` | `oklch(0.285 0.015 265)` |
| `--panel` | `oklch(0.225 0.013 265 / 0.78)` |
| `--panel-strong` | `oklch(0.225 0.013 265 / 0.9)` |
| `--border` | `oklch(0.315 0.014 265)` |
| `--border-strong` | `oklch(0.4 0.016 265)` |
| `--text` | `oklch(0.955 0.004 265)` |
| `--muted` | `oklch(0.71 0.012 265)` |
| `--faint` | `oklch(0.58 0.012 265)` |
| `--accent` | `#03DAC6` |
| `--accent-hover` | `oklch(0.9 0.13 180)` |
| `--accent-fg` | `#000000` |
| `--accent-soft` | `oklch(0.32 0.06 185)` |
| `--accent-border` | `oklch(0.45 0.08 185)` |
| `--pos` | `#4ADE80` |
| `--pos-soft` | `oklch(0.32 0.07 150)` |
| `--neg` | `oklch(0.7 0.17 22)` |
| `--neg-soft` | `oklch(0.33 0.08 20)` |
| `--neu` | `oklch(0.72 0.012 265)` |
| `--neu-soft` | `oklch(0.3 0.008 265)` |
| `--warn` | `oklch(0.82 0.12 80)` |
| `--warn-soft` | `oklch(0.33 0.05 80)` |
| `--shadow` | `0 1px 2px oklch(0 0 0 / 0.4), 0 12px 32px -14px oklch(0 0 0 / 0.6)` |
| `--shadow-sm` | `0 1px 2px oklch(0 0 0 / 0.35)` |

### Variantes de acento (opcionales, atributo `data-accent`)
- `morado` (default): tokens de arriba.
- `indigo`: `--accent: #3700B3`, hover `#24007a`; en oscuro `oklch(0.64 0.2 288)`.
- `teal`: `--accent: #018786` con `--accent-fg:#ffffff`; en oscuro `#03DAC6` con `--accent-fg:#000000`.

Origen de la paleta: set Material-like provisto por el cliente (`#6200EE`, `#3700B3`, `#03DAC6`, `#018786`, error `#B00020`). `--pos` se separó a verde estándar para no colisionar con el teal del acento en oscuro.

### Tipografía
- **IBM Plex Sans** (400/500/600) — toda la interfaz.
- **IBM Plex Mono** (400/500) — siglas, fechas, conteos, URLs, etiquetas de sección, endpoints.
- Google Fonts: `family=IBM+Plex+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400&family=IBM+Plex+Mono:wght@400;500&display=swap`

| Rol | Valor |
|---|---|
| Título de pantalla (Fundamentos) | 34 / 600 / `letter-spacing:-0.02em` |
| Título de sección (h1 de tab) | 19 / 600 / `-0.01em` |
| Titular de artículo analizado | 22 / 600 / line-height 1.3 / `-0.015em` / `max-width:52ch` |
| Subtítulo de card | 15–15.5 / 600 |
| Valor de stat card (encuadre) | 15 / 600 / line-height 1.25 |
| Cuerpo / descripciones | 14.5 / 400 / line-height 1.65 |
| Texto de tabla e inputs | 13–13.5 / 400 (título de fila 500) |
| Metadatos, ayuda | 12–12.5 / 400 |
| Badges | 11.5 / 600 |
| Etiqueta de sección (mono) | 10.5–11 / 500 / `letter-spacing:0.12em` / uppercase / color `--faint` |
| Wordmark ODIN | login 44 / 600 / `letter-spacing:0.22em`; nav 14 / 600 / `0.16em` |

### Espaciado, radios, sombras
- Padding de card 18–22px (headers de panel `18px 20px`; celdas de tabla `12px 14px`, primera/última columna 20px).
- Gaps: 22px entre módulos, 16px entre sub-secciones, 10–12px en grids de cards, 6–9px entre controles.
- Grids: `repeat(auto-fit, minmax(200px,1fr))` stat cards de encuadre · `minmax(300px,1fr)` cards de entidad · `minmax(168px,1fr)` barra de filtros.
- Ancho máximo del workspace **1180px**, centrado, padding lateral 24px. Login 396px. Fundamentos 1080px.
- Radios: 12px paneles · 10px cards de fundamentos · 9px cajas internas y stat cards · 7px controles/botones/inputs · 5–6px badges y chips · 999px nav pill y badge de estado.
- Bordes: siempre `1px solid var(--border)`; `1px dashed var(--border-strong)` en los selects de corrección (señal de "editable").
- `text-wrap: pretty` en titulares y párrafos.

### Translucidez y rendimiento (importante)
- Cards y módulos usan `--panel` **sin** `backdrop-filter` — la translucidez sola deja ver el fondo y cuesta cero.
- `backdrop-filter: blur(12–14px)` solo en **3** elementos: nav pill (`--panel-strong`, blur 12), card de login (blur 14), diálogo (blur 14). No extenderlo: con el canvas animado detrás, cada región borrosa se repinta por frame.

---

## Fondo Plasma (React Bits)
Reemplaza `Aurora`/`SoftAurora`. Componente en `Plasma.jsx`; dependencia `ogl` (ya en el repo). Dos usos, ambos `pointer-events:none` y detrás del contenido:

1. **Login** — pantalla completa: `color={accentHex} speed={0.5} scale={1.9} opacity={theme==='dark'?0.55:0.4} direction="forward"`. Encima, viñeta que lo funde al fondo: `radial-gradient(ellipse 70% 60% at 50% 45%, transparent 0%, var(--bg) 78%)`.
2. **Workspace** — solo una **banda de 420px** anclada arriba (detrás del nav), `overflow:hidden`, `z-index:0`, contenido en `z-index:1`: `color={accentHex} speed={0.35} scale={2.6} opacity={theme==='dark'?0.2:0.14}`. Encima: `linear-gradient(to bottom, transparent 0%, var(--bg) 88%)`. Nunca detrás de las tablas.

`accentHex`: `#6200EE` en claro, `#03DAC6` en oscuro.

Defaults de performance ya aplicados: `renderScale 0.5`, `maxDpr 1.5`, `targetFps 30`, `iterations 44`, `mouseInteractive false`. Respeta `prefers-reduced-motion` (pinta un frame y para), pausa con IntersectionObserver y `visibilitychange`, y maneja pérdida de contexto WebGL. **No subir `targetFps` ni `renderScale`.** Mantener un toggle (setting o constante) para apagar el plasma del workspace: es lo primero que se sacrifica en equipos lentos.

---

## Screens / Views

### 1. Login
**Propósito:** autenticar al único operador.
**Layout:** contenedor a pantalla completa, `display:grid; place-items:center`, plasma + viñeta al fondo. Columna centrada de 396px (padding `0 24px 40px`).
- Wordmark **ODIN** 44/600, `letter-spacing:0.22em` (+ `padding-left:0.22em` para compensar), shimmer: `linear-gradient(100deg, var(--text) 20%, var(--accent) 45%, var(--text) 70%)`, `background-size:200% 100%`, `background-clip:text`, animación `odinShimmer 6s linear infinite` (`background-position` de `-200% 0` a `200% 0`).
- Subtítulo "Monitoreo y análisis de prensa dominicana", 13, `--muted`. Gap 8px, margen inferior 26px.
- Card: `--panel-strong` + blur 14, radio 12, `--shadow`, padding `26px 24px`.
  - "Iniciar sesión" 15/600; ayuda "Ingrese las credenciales del operador." 12.5 `--muted`, margen inferior 20px.
  - Campos en columna gap 14: label 12/500 `--muted` + input (`--surface-2`, borde 1px, radio 7, padding `9px 11px`, 13.5). Password con placeholder `••••••••`.
  - Alerta de error (`role="alert"`): `--neg-soft`, borde `--neg`, radio 7, padding `10px 12px`, 12.5, texto `--neg`; "**Error** Credenciales inválidas o sin conexión con la API."
  - Botón submit ancho completo: `--accent`/`--accent-fg`, radio 7, padding `11px 16px`, 13.5/600. "Entrar" → "Verificando…".
  - Pie tras `border-top`: "Acceso restringido a un operador. El sistema no permite crear cuentas ni recuperar contraseñas." 11.5 `--faint`, line-height 1.5.
**Estados:** idle · verificando · error inline. Sin "recordarme" ni recuperación.

### 2. Workspace — shell y navegación
- Fondo `--bg` + banda de plasma superior. Contenido `max-width:1180px`, padding `22px 24px 80px`, columna gap 22.
- **Nav pill** `position:sticky` (en la app real: **top 16px**), z-index 40, `--panel-strong` + blur 12, borde 1px, radio 999, `--shadow`, padding `7px 8px 7px 18px`, `display:flex; align-items:center; gap:14px`.
  - Wordmark "ODIN" 14/600 `letter-spacing:0.16em`, `padding-right:6px`.
  - Tabs (`nav`, `display:flex; gap:2px; flex:1`): botones `display:inline-flex; align-items:center; gap:7px`, padding `7px 15px`, radio 999, 13px. Activo `background:var(--accent); color:var(--accent-fg); font-weight:600`; inactivo transparente, `--muted`, 500.
  - Contador por tab (ej. Reportes) como chip **en flujo** (mono 10.5, `--accent-fg` si activo / `--faint` si no). No posicionarlo en absoluto: se solapa con el label.
  - Derecha: "operador" (mono 11, `--faint`) + botón circular 30×30 de logout (`--surface-2`, borde 1px, radio 999, hover `color/border: --neg`, `aria-label="Cerrar sesión"`) que abre **diálogo de confirmación**.
- Tabs: Analizar · Reportes · Entidades · Siglas. Conviene añadir **router** (`/analizar`, `/reportes`, `/reportes/:id`, `/entidades`, `/siglas`) para deep-linking; el prototipo usa estado local.

### 3. Analizar
**Card de entrada** (`--panel`, radio 12, padding 22, `--shadow-sm`):
- h1 "Analizar artículo" 19/600 + `POST /api/articles/analyze` en mono 11 `--faint` al lado (baseline compartida).
- Párrafo: "Pegue la URL de la noticia. El sistema extrae el contenido y devuelve sentimiento, encuadre y actores para su revisión antes de guardar." 13 `--muted`, `max-width:70ch`, margen inferior 16.
- Fila `display:flex; gap:9px; flex-wrap:wrap`: input `flex:1; min-width:260px`, **mono 13**, padding `11px 13px`, radio 8, placeholder `https://www.diariolibre.com/…` + botón primario "Analizar" (padding `11px 20px`, radio 8, 13.5/600).
- **Cargando:** debajo, tras `border-top` (padding-top 18): spinner 12×12 (borde 2px `--border-strong`, `border-top-color: --accent`, `odinSpin .8s linear infinite`) + "Extrayendo y analizando con el modelo — puede tardar hasta un minuto." 12.5 `--muted`; luego 4 barras skeleton (alturas 13/11/11/11, anchos 55/100/88/40%, radio 4, `--surface-3`, `odinPulse 1.6s` con delays 0/.15/.3/.45s). Botón muestra "Analizando…".

**Card de análisis** — misma pieza para borrador editable, guardado y detalle de reporte: un solo componente con prop `editable`.
- Barra de acciones sobre la card: `← Volver a la lista` (solo en detalle) · **badge de estado** pill: "Vista previa · sin guardar" (`--accent-soft`/`--accent`/`--accent-border`) o "Guardado en el archivo" / "Reporte guardado" (`--pos-soft`/`--pos`) · a la derecha, si `editable`: "Descartar" (secundario) + "Guardar reporte" (primario).
- Card `--panel`, radio 12, `overflow:hidden`, secciones separadas por `border-bottom`:
  1. **Cabecera** (padding `22px 24px`): badge de sentimiento (`Positivo/Negativo/Neutro` + ` · NN%` si no es neutro) + si `editable`, select punteado para corregirlo (POS/NEU/NEG). Titular 22/600 (link al original). Metadatos en fila `gap:0 18px`, 12.5: `Fuente` · `Autor` · `Sección` · `Publicado` (etiqueta en `--faint`, valor en `--muted`) + link mono "ver original ↗" (`target="_blank" rel="noreferrer"`).
  2. **Tema y palabras clave** (grid `minmax(220px,1fr)`, gap 20): etiqueta mono + input (editable) o texto 13.5/500; keywords como chips `--surface-2`, borde 1px, radio 5, 11.5 `--muted` (el backend manda un string separado por comas — split en el cliente).
  3. **Análisis de encuadre**: etiqueta mono + "Cómo el medio construye la historia". Grid de **4 stat cards** (`minmax(200px,1fr)`, gap 12); fondo/borde/color según el **tono del valor**: label 11/600 uppercase `--faint`; valor 15/600 en el color del tono; barra de peso de 3px (`--border` de fondo, relleno del color del tono: 82% / 64% / 55% / 48% para marco / titular / lead / fuentes); si `editable`, select punteado con las opciones del enum.
     - Tono → color: **neg** (`crisis_conflicto`, `negligencia`, `denuncia`, `alarmista`, `sensacionalista`, `sin_fuentes`) · **pos** (`logro_institucional`, `crecimiento`, `informativo`, `tecnico`, `citas_directas`, `datos_duros`) · **warn** (`oficialista`, `testimonios_anonimos`) · **neu** (`neutro_informativo`, `social`, `mixtas`).
     - Etiquetas ES: Marco narrativo / Intención del titular / Orientación del lead / Calidad de fuentes. Valores: Crisis / conflicto, Logro institucional, Negligencia, Crecimiento, Denuncia, Neutro informativo · Informativo, Alarmista, Sensacionalista · Social, Oficialista, Técnico · Citas directas, Testimonios anónimos, Datos duros, Mixtas, Sin fuentes.
     - **Unificar estos mapas de etiquetas en un módulo compartido** (hoy duplicados en `App.tsx` y `ReportsList.tsx`).
  4. **Actores** (grid `minmax(190px,1fr)`, `align-items:end`): "Actor dominante", "Actor señalado", "Actor acreditado" — label 11/500 `--faint` + input o texto 13/500. Al lado, chip "Datos duros" con valor Sí/No coloreado por tono (pos si sí, neu si no), no editable.
  5. **Cuerpo del artículo**: etiqueta mono + caja `max-height:230px; overflow:auto`, `--surface-2`, borde 1px, radio 9, padding `16px 18px`, 13.5/1.7 `--muted`, párrafos con `margin-bottom:12px`.
- **Card de entidades** aparte (`--panel`, radio 12, padding `20px 24px`): h3 "Figuras y empresas mencionadas" 15/600 + "N detectadas" mono 11 `--faint`. Grid `minmax(300px,1fr)`, gap 12. Cada card: `--surface-2`, borde 1px, radio 9, padding 14, columna gap 9.
  - Nombre 14/600 + si `extraction_confidence < 0.9`, chip "revisar" (`--warn-soft`/`--warn`, 10.5/600, `title="Confianza de extracción baja — revisar"`).
  - Meta: tipo (Persona/Organización) · "N menciones" (mono), 11.5 `--faint`.
  - Badge de `sentiment_toward` a la derecha, mismo sistema de colores.
  - Cita de contexto si existe: `border-left:2px solid var(--border-strong)`, `padding-left:11px`, 12.5 itálica 1.55 `--muted`.
  - Si `editable`: botones "Editar" / "Quitar" (11.5, `--surface`, borde 1px, radio 6; Quitar en hover → `--neg`).
- Variante **`already_saved`**: idéntica sin inputs/selects/acciones, badge "Reporte guardado".

### 4. Reportes
**Barra de filtros** (`--panel`, radio 12, padding 18): h1 "Reportes" 19/600 + "X de Y reportes" 12.5 `--faint` + "Limpiar filtros" a la derecha (secundario 12.5, visible solo con filtros activos).
Grid `repeat(auto-fit, minmax(168px,1fr))`, gap 10: input "Título o tema…", input "Entidad mencionada…", y 8 selects (Todas las fuentes — de `/api/articles/filters` —, Todo sentimiento, Todo encuadre, Todo titular, Todo lead, Toda calidad de fuente, "Datos duros: todos/con/sin", orden Más recientes/Más antiguos).
**Select propio:** wrapper `position:relative`; `select` con `appearance:none`, padding `8px 28px 8px 11px`, `--surface-2`, borde 1px, radio 7, 13px, `cursor:pointer`; chevron `▾` 10px `--faint` en `position:absolute; right:10px; top:50%; translateY(-50%); pointer-events:none`. (Alternativa válida: `Select` de shadcn con estos tokens.)
**Fechas:** `label` que envuelve el input — caja `--surface-2`, borde 1px, radio 7, con texto "Desde"/"Hasta" 11.5 `--faint` + `input type="date"` transparente sin borde. Un date input vacío no comunica nada por sí solo.
Debounce de **300ms** en los campos de texto.

**Tabla** (`--panel`, radio 12, `overflow:hidden`, `border-collapse:collapse`, 13px):
- `thead`: fila `--surface-2`, celdas mono 10.5/500 uppercase `letter-spacing:0.1em`, `--faint`, padding `10px 14px`, `border-bottom`, `cursor:pointer`, `user-select:none`, `white-space:nowrap`. Columna ordenada: color `--accent` + flecha ` ↑`/` ↓`. Click alterna desc→asc.
- Columnas: **Fecha** (mono 11.5 `--faint`, formato `27 jul 26`) · **Artículo** (título 500/1.4 + tema 12 `--muted` debajo, `max-width:380px`) · **Fuente** (`--muted`) · **Sentimiento** (badge) · **Encuadre** (chip neutro) · **Ent.** (mono, derecha) · **Datos** (centrada: `●` en `--accent` si `has_hard_data`, `—` en `--faint` si no).
- Filas: `cursor:pointer`, `border-bottom:1px solid var(--border)`, hover `--surface-2`, celdas padding `12px 14px`, `vertical-align:top`. Click → detalle.
- Pie: `--surface-2`, `border-top`, padding `11px 14px`: "Página X de Y · N visibles" 12 `--faint` + Anterior/Siguiente (12.5, `--surface`, borde 1px, radio 6). 12 por página; ocultar con una sola.
- **Vacío:** dentro de la card, columna centrada padding `56px 20px`: "Sin resultados" 14.5/600 + "Ningún reporte coincide con los filtros aplicados." 13 `--muted` `max-width:38ch` + botón "Quitar filtros".
- **Cargando:** 4–8 filas skeleton con el mismo `odinPulse`.
**Detalle:** reusa la card de análisis en modo lectura, con "← Volver a la lista" arriba.

### 5. Entidades canónicas
Panel `--panel` radio 12 `overflow:hidden`. Header (padding `18px 20px`, `border-bottom`): h1 "Entidades canónicas" 19/600 + "Catálogo deduplicado de figuras y organizaciones" 12.5 `--faint` + input "Buscar entidad…" (200px); añadir el select de tipo Persona/Organización.
Filas densas (`display:flex; align-items:center; gap:12px; padding:14px 20px; border-bottom`, hover `--surface-2`): chevron de expandir · nombre 14/600 + chip de tipo (10.5) + descripción 12 `--muted` truncada con ellipsis · stats mono 11.5 `--faint` "48 art. · 214 menc." · botones "Fusionar" / "Editar" (11.5, `--surface-2`, borde 1px, radio 6).
Conservar comportamientos actuales: expandir carga on-demand los artículos vinculados; editar convierte la fila en inputs inline (nombre + descripción con check/cancelar); fusionar abre panel inline con buscador de destino (mismo tipo, excluyendo la actual, hasta 8 coincidencias con su conteo) → **diálogo propio** de confirmación.

### 6. Siglas
Panel `--panel` radio 12. Header: h1 "Siglas" + "N siglas · M activas" 12.5 `--faint` + input "Buscar sigla…" (180px, debounce 300ms) + botón primario "Nueva sigla" (se convierte en formulario inline: sigla forzada a mayúsculas, nombre canónico, tipo).
Tabla: **Sigla** (mono 500, padding lateral 20) · **Nombre canónico** (`--muted`) · **Tipo** (chip) · **Acciones** (derecha): "Activa"/"Inactiva" (`--pos` / `--faint`), "Editar" (inline), "Eliminar" (hover `--neg`) → diálogo propio. Filas inactivas `opacity:0.45`.

### 7. Fundamentos (documentación interna, opcional)
Ancho 1080px; secciones con `h2` 16/600 + descripción 12.5 `--faint` sobre `border-bottom`: swatches de tokens (grid `minmax(150px,1fr)`, muestra de 56px + nombre 12.5 + token mono 10.5), escala tipográfica (grid `120px 1fr` con el valor en mono a la izquierda), componentes (botones, badges, campos y selects) y estados unificados (cargando / error / vacío) + demo del diálogo. Útil como ruta `/fundamentos`; si no se implementa, el HTML queda como referencia.

---

## Interactions & Behavior
- **Navegación:** tabs del pill nav; en Reportes, click en fila → detalle, "Volver" → lista (idealmente rutas reales).
- **Analizar:** submit → cargando (skeleton + spinner + copy de espera) → borrador editable → "Guardar reporte" → badge "Guardado en el archivo" y desaparecen los controles de edición. "Descartar" vuelve al estado inicial. URL ya existente → variante `already_saved` de solo lectura.
- **Edición inline** (entidades y siglas): se mantiene; no reemplazar por modales.
- **Diálogo propio** (sustituye `window.confirm`): overlay `position:fixed; inset:0; z-index:100`, `background: oklch(0.2 0.02 265 / 0.5)`, `backdrop-filter: blur(2px)`, `display:grid; place-items:center`, padding 24. Panel máx 400px, `--panel-strong` + blur 14, radio 12, `--shadow`, padding 22, entrada `odinIn .16s ease`. Título 15.5/600, cuerpo 13/1.6 `--muted`, acciones a la derecha gap 9: "Cancelar" (secundario) + confirmar (primario, o `--neg` con texto blanco si es destructivo). Click en el overlay cierra. **Pendiente al implementar:** focus trap, `Esc` para cerrar, `role="dialog" aria-modal="true"`, foco inicial en Cancelar. Copys: "Eliminar la sigla MINERD?" / "Fusionar “X” con “Y”?" (siempre explicar la consecuencia: menciones transferidas, acción no reversible) / "Cerrar sesión?" ("Se descartará cualquier análisis en vista previa que no haya guardado.").
- **Animaciones** (con `prefers-reduced-motion` respetado): `odinPulse` 1.6s ease-in-out (skeletons, opacidad .55↔1) · `odinSpin` .8s linear · `odinIn` .16–.24s ease (`translateY(6px)` → 0) · `odinShimmer` 6s linear (solo wordmark) · plasma. Nada más se anima.
- **Hover:** primario → `--accent-hover`; secundario → `--surface-3`; fantasma → `--surface-2` + `--text`; destructivo → `--neg-soft` o `color/border: --neg`; fila de tabla → `--surface-2`.
- **Focus:** `outline: 2px solid var(--accent); outline-offset: 1px` en inputs, selects y botones (`:focus-visible`).
- **401 en cualquier llamada** → vuelta forzada al login (evento global `odin:auth-expired`), sin cambios.
- **Accesibilidad:** botones de solo ícono con `aria-label`; alertas con `role="alert"`; contraste verificado en ambos temas.
- **Responsive:** pensado para escritorio. El nav pill debe colapsar por debajo de ~768px y la tabla pasar a scroll horizontal o cards de fila; no es prioridad.

## State Management
- **Global:** `theme: 'light' | 'dark'` (persistir en `localStorage`, aplicar `data-theme` en la raíz; default claro), token JWT, `dialog: {title, body, confirm, danger, onConfirm} | null`.
- **Analizar:** `url`, `stage: 'idle' | 'loading' | 'result'`, `saved`, y el borrador editable (`overall_sentiment`, `main_topic`, `framing`, `headline_intent`, `lead_orientation`, `source_quality`, los 3 actores, `entities[]` con eliminación local).
- **Reportes:** `q`, `qEntity`, `fSource`, `fSent`, `fFraming`, `fHeadline`, `fLead`, `fSourceQ`, `fHard`, `dateFrom`, `dateTo`, `sortKey`, `sortDir`, `page`, `selectedId`. Filtrado, orden y paginación van **en el backend** (el prototipo los hace en cliente solo para demostrar la UI).
- **Entidades / Siglas:** lista + `expandedId`, `editingId`, `mergeTargetId`, búsqueda con debounce.
No inventar campos: lo que no exista en `api-types.ts` es cambio de backend, no de UI.

## Assets
- Fuentes **IBM Plex Sans** e **IBM Plex Mono** (Google Fonts o `@fontsource`). Sustituyen a Geist.
- Iconos: seguir con **lucide** (chevron, GitMerge, lápiz, toggle, power, alerta). En el prototipo hay glifos de texto (`▾ ▸ ⏻ ● ↗`) como stand-in — reemplazar por iconos lucide de 14–16px con `currentColor`.
- `Plasma.jsx` (React Bits adaptado; dependencia `ogl`). Sin imágenes ni ilustraciones: el producto no usa imagery.

## Files
- `Odin.dc.html` + `support.js` — prototipo hifi completo (Fundamentos / Login / Workspace con las 4 áreas, ambos temas, diálogo, estados). Abrir en el navegador; el selector superior y el toggle de tema son herramientas de revisión.
- `Plasma.jsx` — componente de fondo listo para copiar al repo (lee `window.ogl`; en el repo usa `import { Renderer, Program, Mesh, Triangle } from 'ogl'` y borra el helper `waitForOgl`).
- `DESIGN_HANDOFF.md`, `CONTEXT_README.md` — handoff original del estado previo (inventario de pantallas, flujo, contrato de datos). Sigue siendo la referencia de comportamiento y del modelo de datos.

## Qué se elimina del front actual
`Aurora.tsx`, `SoftAurora.tsx`, `PillNav.css` (colores oklch hardcodeados), `ShimmerText` como componente aparte (el shimmer es un estilo del wordmark), `InteractiveHoverButton` (ancho fijo `w-32` que rompía con "Analizando…"), los `<select>` nativos sin estilo y todos los `window.confirm()`. Los mapas de etiquetas duplicados entre `App.tsx` y `ReportsList.tsx` pasan a un módulo único.
