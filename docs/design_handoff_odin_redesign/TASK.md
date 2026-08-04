# Task: rediseño de UI de Odin

> Ejecutar guiándose por el handoff de esta misma carpeta — no reinventar el
> alcance, ya está decidido. Leer en este orden antes de tocar código:
> 1. **README.md** — spec principal (tokens, tipografía, las 6 pantallas, estados, interacciones). Es la fuente de verdad para valores exactos (colores, spacing, radios, copys).
> 2. **DESIGN_HANDOFF.md** — inventario del frontend *tal como existe hoy* (qué archivo hace qué, qué está duplicado, qué es libre vs. fijo).
> 3. **Odin.dc.html** (+ `support.js` para abrirlo en navegador) — prototipo hifi de referencia visual. **Es referencia, no código a copiar tal cual** (usa un pseudo-framework propio, `sc-if`/`sc-for`/`style-hover`); hay que recrearlo con React/Tailwind/shadcn reales.
> 4. **Plasma.jsx** — este sí es código real: portar a TSX casi literal (ver nota abajo).

Los endpoints, formas de datos, valores de enum y el flujo de auth (JWT en
localStorage, 401 → login) **no cambian**. `frontend/src/lib/odin-api.ts` y
`api-types.ts` siguen siendo la fuente de verdad — no inventar campos.

## Decisiones de alcance ya confirmadas con el usuario (no volver a preguntar)

- **Sin router.** Se mantiene navegación por estado local (`tab` en `useState`), como hoy. No instalar `react-router-dom`.
- **Con toggle de tema.** Agregar un control claro/oscuro visible en el nav (icono sol/luna), persistido en `localStorage`. El wireframe del HTML no lo muestra (solo tiene un selector en la barra de revisión del prototipo, que no es parte de la app), pero el modelo de estado del handoff sí lo pide.
- **Sin pantalla `/fundamentos`.** No implementar esa ruta; el HTML queda solo como referencia visual de tokens/componentes.

## Plan de ejecución

### 1. Tokens y fundaciones (`frontend/src/index.css`)
- `npm uninstall @fontsource-variable/geist gsap motion` (quedan sin uso tras el paso 5).
- `npm install @fontsource/ibm-plex-sans @fontsource/ibm-plex-mono`, importar los pesos 400/500/600/700 + 400-italic (Sans) y 400/500 (Mono).
- Definir los tokens primitivos del handoff (`--bg`, `--surface(-2/-3)`, `--panel(-strong)`, `--border(-strong)`, `--text`, `--muted`, `--faint`, `--accent(-hover/-fg/-soft/-border)`, `--pos/-neg/-neu/-warn` + `-soft`, `--shadow(-sm)`) con los valores exactos de README §Design Tokens. Usar `[data-theme="dark"]` (atributo, no clase `.dark`) — actualizar `@custom-variant dark (&:is([data-theme="dark"] *))`.
- Puentear alias semánticos de shadcn a los primitivos (`--background:var(--bg)`, `--primary:var(--accent)`, `--card:var(--panel)`, `--destructive:var(--neg)`, `--success:var(--pos)`, `--warning:var(--warn)`, etc.) para no reescribir `Button`/`Badge`/`Card`/`Alert`/`Input`/`Separator`/`Skeleton`.
- `@keyframes odinPulse/odinSpin/odinShimmer/odinIn` exactos del prototipo (`Odin.dc.html:84-88`), respetando `prefers-reduced-motion`.
- Radios: no forzar la escala `--radius-*` existente, usar valores arbitrarios de Tailwind (`rounded-[12px]`, `rounded-[9px]`, `rounded-[7px]`, `rounded-[5px]`, `rounded-full`) por componente según README §Espaciado/radios.

### 2. Piezas compartidas nuevas
- `frontend/src/lib/labels.ts` — unifica `FRAMING_LABELS`/`HEADLINE_LABELS`/`LEAD_LABELS`/`SOURCE_LABELS`/`SENTIMENT_LABELS` (hoy duplicados en `App.tsx` y `ReportsList.tsx`) + mapa `TONE` (literal de `Odin.dc.html:667-673`) + helper `toneVars(tone)`.
- `frontend/src/lib/format.ts` — `formatDateShort` (tabla, "27 jul 26"), `formatDateFull` (cabecera/artículos vinculados), `isLowConfidence` (`<0.9`). Reemplaza las 3 implementaciones de `formatDate` repartidas hoy.
- `frontend/src/lib/dialog.tsx` — `DialogProvider` + hook `useConfirm()` (`confirm({title, body, confirmLabel, danger}) => Promise<boolean>`), reemplaza `window.confirm`/`confirm()`. Overlay+panel exacto de `Odin.dc.html:646-657`. Implementar lo que el handoff marca "pendiente": focus trap, `Esc` cierra, `role="dialog" aria-modal`, foco inicial en Cancelar, click en overlay cierra.
- `frontend/src/components/ui/select.tsx` — wrapper propio de `<select>` (spec "Select propio", README §4) con chevron custom; reemplaza los 4 `selectClass` locales duplicados e inconsistentes (`ring-2` vs `ring-3`) en `App.tsx`/`ReportsList.tsx`/`CanonicalEntityManager.tsx`/`AliasManager.tsx`. Modo "dashed" para selects de corrección inline.
- `frontend/src/components/Plasma.tsx` — port TS de `Plasma.jsx`: `import { Renderer, Program, Mesh, Triangle } from 'ogl'` en vez de `window.ogl`/`waitForOgl` (se borra ese helper). No tocar el resto de la lógica (perf defaults, `prefers-reduced-motion`, pausa por `IntersectionObserver`/`visibilitychange`, recuperación de contexto WebGL perdido).
- `frontend/src/components/Nav.tsx` — reemplaza `PillNav.tsx`/`.css`. Pill sticky con wordmark, tabs, botón de tema, "operador", logout con `useConfirm()`. Sin animación GSAP de burbuja (no está en el wireframe); retirar `gsap`.
- `frontend/src/components/AnalysisCard.tsx` + `EntitiesCard.tsx` — pieza única (prop `editable`) para cabecera+tema+encuadre+actores+cuerpo y para la grilla de entidades mencionadas. Reemplaza la duplicación entre la vista de resultado de `App.tsx` y `ReportDetail` de `ReportsList.tsx`. En `EntitiesCard`, cada entidad pasa de "siempre editable" a patrón Editar/Quitar → inline-edit (igual que `CanonicalEntityManager`/`AliasManager`); el HTML no wireframea ese estado expandido, así que se sigue el patrón ya usado en el resto de la app.

### 3. Pantallas
- **Login** (`LoginScreen.tsx`): Plasma full-screen + viñeta, wordmark shimmer CSS puro (sustituye `ShimmerText`/`motion`), card, formulario, botón ancho completo (sustituye `InteractiveHoverButton`). Mismo contrato de props.
- **Workspace shell** (`App.tsx`): estado `theme` persistido + `data-theme` en `<html>`; envolver en `DialogProvider`; pantalla "checking auth" sin Plasma (evita montar/desmontar WebGL en una vista transitoria); banda Plasma de 420px en el workspace con constante local para apagarla (sin UI). Migrar labels/format a los módulos nuevos.
- **Analizar**: card de entrada con estados exactos (spinner `odinSpin` + 4 skeleton bars `odinPulse` escalonadas); barra de acciones sobre `AnalysisCard`+`EntitiesCard`; misma lógica de datos (`handleSubmit`/`toDraft`/`handleSave`/`OdinApiError`), solo cambia el layout.
- **Reportes** (`ReportsList.tsx`): `FilterBar` con el `Select` nuevo y layout de grid del README §4; tabla con cabecera mono uppercase + indicador de orden; `ReportDetail` pasa a usar `AnalysisCard editable={false}` + `EntitiesCard editable={false}`. Debounce 300ms y estados cargando/error/vacío se preservan.
- **Entidades canónicas** (`CanonicalEntityManager.tsx`): restyle de filas/badges/botones/Select; toda la lógica se preserva; `MergePanel.handleMerge` pasa a `useConfirm()`.
- **Siglas** (`AliasManager.tsx`): restyle de tabla/formulario inline (mayúsculas intactas); toda la lógica se preserva; `AliasRow.handleDelete` pasa a `useConfirm()`.
- **`SentimentBadge.tsx`**: retoken a `bg-[var(--pos-soft)] text-[var(--pos)] border border-[var(--pos)]` (y NEG/NEU equivalentes) en vez de las opacidades `/15`/`/30` actuales.

### 4. Se elimina
`Aurora.tsx`, `SoftAurora.tsx`+`.css`, `PillNav.tsx`+`.css`, `components/ui/shimmer-text.tsx`, `components/ui/interactive-hover-button.tsx`, las 4 copias de `selectClass`/label maps. `npm uninstall gsap motion @fontsource-variable/geist` (confirmar con grep antes que nada más los use).

### 5. Verificación
1. `cd frontend && npm install && npm run build` (type-check `tsc -b` incluido).
2. `npm run dev` + backend (`.venv/bin/python main.py` desde la raíz) y recorrer manualmente: login → Analizar (URL nueva y URL ya guardada) → Reportes (filtros/orden/paginación/detalle) → Entidades (expandir/editar/fusionar con diálogo) → Siglas (crear/editar/activar-desactivar/eliminar con diálogo) → toggle de tema (persiste al recargar) → logout (con diálogo).
3. Revisar ambos temas en cada pantalla; Plasma respeta `prefers-reduced-motion` y no queda por encima de tablas/formularios.

## Notas de contexto (por qué estas decisiones)
- No hay `--success`/`--warning` en modo claro en el CSS actual, y no hay ningún mecanismo de theme-toggle hoy en el código — ambos se resuelven de raíz al puentear los tokens semánticos a los primitivos nuevos en el paso 1.
- Hoy existen 4 copias de `selectClass` (2 variantes distintas de `ring`) y 2 copias completas de los label maps de enums — el paso 2 los consolida en un solo lugar cada uno.
- Los dos únicos usos de `confirm()`/`window.confirm` en todo `frontend/src` son `AliasManager.tsx` (eliminar sigla) y `CanonicalEntityManager.tsx` (fusionar entidad) — el diálogo propio del paso 2 cubre ambos, más logout (nuevo).
