# Odin Frontend — ViewSource Plan

> **Contexto**: revisión completa del código fuente del frontend (React 19 + TypeScript 6 + Vite 8 + TailwindCSS v4 + shadcn). El objetivo es catalogar deuda técnica real con suficiente detalle para atacarla en PRs atómicos, sin romper nada.
>
> Stack relevante: `react-router-dom@7`, `@tanstack/react-query@5`, `ogl@1`, `framer-motion@12`, `oxlint`, `vitest`.

---

## Leyenda de severidad

| Símbolo | Significado |
|---------|-------------|
| 🔴 | Bug o comportamiento incorrecto — arreglar antes de la siguiente release |
| 🟡 | Deuda técnica — afecta mantenibilidad, DX o accesibilidad |
| 🟢 | Nice-to-have — mejora sin urgencia |

---

## Grupo 1 — Bugs / Comportamiento incorrecto

### 🔴 VS-01 · `index.html`: `lang="en"` en una UI enteramente en español

**Archivo**: [`frontend/index.html:2`](../frontend/index.html)

**Problema**: El atributo `lang` le dice al browser y a los lectores de pantalla qué idioma usar para síntesis de voz, corrección ortográfica y heurísticas de guionado. Con `lang="en"` un lector de pantalla pronunciará "Analizar", "Ajustes" o "Sentimiento" con fonética inglesa.

```diff
-<html lang="en" class="dark">
+<html lang="es">
```

**Nota sobre `class="dark"`**: el sistema de temas usa `document.documentElement.dataset.theme = "light"|"dark"` (selector CSS `[data-theme="dark"]`). La clase `dark` del HTML inicial no matchea ningún selector propio y es letra muerta. Puede confundir a quien integre un plugin de shadcn que sí espere `.dark`. Quitar en el mismo commit.

---

### 🔴 VS-02 · Nav items usan `<button onClick={navigate}>` en vez de `<Link>`

**Archivo**: [`frontend/src/components/Nav.tsx:54-76`](../frontend/src/components/Nav.tsx)

**Problema**: La navegación entre rutas se hace con `<button type="button" onClick={() => onTabChange(tab)}>`, que por dentro llama a `navigate(tab)` de react-router. Esto rompe tres contratos implícitos del browser:

1. **Clic del medio** (abrir en nueva pestaña): un `<button>` no puede abrirse en nueva pestaña. Un `<a href>` sí.
2. **Historial**: `navigate()` en `onClick` produce el mismo comportamiento que `<Link>`, pero `<Link>` también gestiona el caso de clic con modificadores (`Ctrl`, `Meta`).
3. **Accesibilidad**: los lectores de pantalla distinguen entre "botón que ejecuta acción" y "enlace que navega". Anunciar los tabs como botones es semánticamente incorrecto.

**Fix**: Reemplazar con `<NavLink to={tab}>` y mover la lógica de estilos activos a `className` recibiendo `{ isActive }`:

```tsx
import { NavLink } from "react-router-dom"

<NavLink
  to={item.tab}
  className={({ isActive }) =>
    cn(
      "inline-flex items-center gap-[7px] rounded-full px-[15px] py-[7px] text-[13px] transition-colors",
      isActive ? "font-semibold" : "font-medium"
    )
  }
  style={({ isActive }) => ({
    background: isActive ? "var(--primary)" : "transparent",
    color: isActive ? "var(--accent-fg)" : "var(--muted-foreground)",
  })}
>
  {item.label}
</NavLink>
```

Esto también elimina la prop `onTabChange` de `Nav` y la lógica `activeTab` de `Layout`, que eran boilerplate del workaround.

---

### 🔴 VS-03 · `AnalysisCard`: `key={i}` en párrafos del cuerpo del artículo

**Archivo**: [`frontend/src/components/AnalysisCard.tsx:278-282`](../frontend/src/components/AnalysisCard.tsx)

**Problema**: Usar el índice como `key` es correcto cuando la lista es **estable y no reordena**. Aquí el texto del artículo sí puede cambiar entre renders (análisis de otra URL, edición) — React puede reutilizar nodos DOM incorrectos y no actualizar el texto correctamente, especialmente si hay transiciones CSS.

```diff
-.map((p, i) => <p key={i} className="text-pretty" ...>{p}</p>)
+.map((p, i) => <p key={`${i}-${p.slice(0, 32)}`} className="text-pretty" ...>{p}</p>)
```

La clave compuesta de índice + prefijo del contenido es estable dentro de un mismo texto y cambia cuando el contenido es distinto.

---

## Grupo 2 — Calidad / DRY / Mantenibilidad

### 🟡 VS-04 · Función `errorMessage` duplicada en 3 páginas

**Archivos**:
- [`AnalyzePage.tsx:31-35`](../frontend/src/pages/AnalyzePage.tsx)
- [`ReportsPage.tsx:68`](../frontend/src/pages/ReportsPage.tsx)
- [`ReportDetailPage.tsx:102-104`](../frontend/src/pages/ReportDetailPage.tsx)

**Problema**: La misma lógica aparece tres veces con ligeras variaciones de nombre y fallback. Si `OdinApiError` cambia de forma, hay que buscar y parchear en tres sitios.

```ts
// Actual (repetido):
err instanceof OdinApiError ? err.message : fallback
```

**Fix**: exportar desde `lib/odin-api.ts`:

```ts
/** Extrae el mensaje de un error de la API, o devuelve el fallback para errores de red. */
export function apiErrorMessage(err: unknown, fallback: string): string {
  return err instanceof OdinApiError ? err.message : fallback
}
```

Impacto: 3 archivos simplificados, un único punto de cambio futuro.

---

### 🟡 VS-05 · Bloque JSX de error `role="alert"` duplicado ~5 veces

**Archivos**:
- [`AnalyzePage.tsx:150-157`](../frontend/src/pages/AnalyzePage.tsx)
- [`ReportsPage.tsx:84-88`](../frontend/src/pages/ReportsPage.tsx)
- [`ReportDetailPage.tsx:172-186`](../frontend/src/pages/ReportDetailPage.tsx) (×3)

**Problema**: El mismo bloque de 6 líneas se copia literalmente con distintos mensajes. Los tokens de diseño (`neg-soft`, `neg`) están dispersos: si el sistema de color cambia, hay que rastrearlos manualmente.

**Fix**: crear `components/ErrorAlert.tsx`:

```tsx
export function ErrorAlert({ title, message }: { title?: string; message: string }) {
  return (
    <div
      role="alert"
      className="rounded-[7px] border px-3 py-2.5 text-[12.5px]"
      style={{ background: "var(--neg-soft)", borderColor: "var(--neg)", color: "var(--neg)" }}
    >
      {title && <strong>{title} </strong>}
      {message}
    </div>
  )
}
```

Uso: `<ErrorAlert title="No se pudo guardar" message={saveError} />`. Reduce ~30 líneas duplicadas.

---

### 🟡 VS-06 · Inline `style={{ color: "var(--faint)" }}` mezclado con Tailwind — 40+ ocurrencias

**Archivos**: prácticamente todos los componentes.

**Problema**: Hay dos sistemas de estilos coexistiendo: clases de Tailwind para layout/spacing y `style={{}}` para tokens del design system. Esto produce ruido visual en el JSX, impide que oxlint detecte inconsistencias y hace imposible usar utilidades de TW como `hover:`, `dark:`, `focus-visible:` sobre tokens propios.

**Causa raíz**: los tokens (`--faint`, `--surface-2`, `--pos`, etc.) no están registrados en `@theme`, así que Tailwind no los conoce.

**Fix**: en `index.css`, dentro del bloque `@theme inline {}` existente, añadir los tokens primitivos de Odin:

```css
@theme inline {
  /* ... tokens existentes de shadcn ... */

  /* Primitivos Odin */
  --color-bg: var(--bg);
  --color-surface: var(--surface);
  --color-surface-2: var(--surface-2);
  --color-surface-3: var(--surface-3);
  --color-text: var(--text);
  --color-faint: var(--faint);
  --color-pos: var(--pos);
  --color-pos-soft: var(--pos-soft);
  --color-neg: var(--neg);
  --color-neg-soft: var(--neg-soft);
  --color-neu: var(--neu);
  --color-neu-soft: var(--neu-soft);
  --color-warn: var(--warn);
  --color-warn-soft: var(--warn-soft);
  --color-panel: var(--panel);
  --color-panel-border: var(--panel-border);
  --color-border-strong: var(--border-strong);
  --color-accent-soft: var(--accent-soft);
  --color-accent-border: var(--accent-border);
  --color-accent-fg: var(--accent-fg);
  --color-accent-hover: var(--accent-hover);
}
```

Después, `style={{ color: "var(--faint)" }}` → `className="text-faint"`, `style={{ background: "var(--surface-2)" }}` → `className="bg-surface-2"`, etc.

> **Estrategia de migración**: hacerlo de forma incremental, archivo por archivo. No intentar migrar todo en un commit — el diff sería ilegible.

---

### 🟡 VS-07 · `getUsername()` lee `localStorage` en cada render de `Layout`

**Archivo**: [`frontend/src/components/Layout.tsx:64`](../frontend/src/components/Layout.tsx)

**Problema**: `getUsername()` accede a `localStorage` directamente en el JSX del render. `App` ya mantiene `username` en estado (`useState`) y lo pasa a `Layout` como prop — pero luego `Layout` lo ignora y vuelve a leer `localStorage` para pasarlo a `Nav`. Es redundante y accede a storage en el hot path del render.

**Fix**: pasar `username` como prop desde `App` → `Layout` → `Nav`:

```tsx
// Layout.tsx — añadir al interface LayoutProps:
interface LayoutProps {
  onLogout: () => void
  theme: Theme
  onToggleTheme: () => void
  username: string | null   // ← nuevo
}

// App.tsx — pasar el state:
<Layout ... username={username} />

// Layout.tsx — bajar a Nav:
<Nav ... username={username} />
```

---

### 🟡 VS-08 · Versión `"beta v2.1.1"` hardcodeada en `Nav`

**Archivo**: [`frontend/src/components/Nav.tsx:46`](../frontend/src/components/Nav.tsx)

**Problema**: La versión de la app está en `package.json` (`"version": "0.0.0"`) y como literal en `Nav.tsx`. Al hacer un release hay que actualizar ambos sitios, y es fácil que diverjan.

**Fix**: Vite expone variables del build vía `define`:

```ts
// vite.config.ts — añadir:
import pkg from "./package.json" with { type: "json" }

export default defineConfig({
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
})
```

```tsx
// vite-env.d.ts o Nav.tsx:
declare const __APP_VERSION__: string

// Uso en Nav.tsx:
<span ...>beta v{__APP_VERSION__}</span>
```

---

### 🟡 VS-09 · `ReportDetailPage`: `article.id as number` — type cast innecesario

**Archivo**: [`frontend/src/pages/ReportDetailPage.tsx:70,87`](../frontend/src/pages/ReportDetailPage.tsx)

**Problema**: El tipo generado por OpenAPI declara `id` como `number | undefined` en `ArticleDetail`. Es un artefacto de cómo `openapi-typescript` convierte campos `required: false` aunque el backend siempre los devuelva. Los dos `as number` silencian el error de tipo en vez de resolverlo — si algún día el backend devuelve `null` en `id`, explotará silenciosamente en runtime.

**Fix en `lib/odin-api.ts`**: sobreescribir el tipo generado con un override más estrecho:

```ts
// Reemplaza el alias existente de ArticleAnalysis:
export type ArticleAnalysis = Omit<components["schemas"]["ArticleDetail"], "id"> & { id: number }
```

Esto elimina todos los `as number` del codebase y hace que TypeScript atrape el caso `id == null` en compilación.

---

### 🟡 VS-10 · `dialog.tsx`: modal implementado con `<div>` — no bloquea a11y fuera del dialog

**Archivo**: [`frontend/src/lib/dialog.tsx`](../frontend/src/lib/dialog.tsx)

**Problema**: El dialog usa `<div role="dialog">` con trap de foco manual (`querySelectorAll`). Funciona para el caso de teclado dentro del panel, pero:

- El contenido fuera del dialog **no queda inaccesible** para lectores de pantalla (no hay `inert` en el resto del árbol DOM).
- No bloquea el scroll del body.
- La trampa de foco puede fallar con elementos dinámicos que cambien su `tabindex` durante la animación de entrada.

**Fix recomendado**: migrar al elemento `<dialog>` nativo con `.showModal()`. Tiene trampa de foco integrada, aplica `inertness` automáticamente al resto del DOM y el backdrop se gestiona con `::backdrop`.

> **Nota**: este cambio tiene la mayor superficie de riesgo de regresión. Reservar para un PR dedicado con tests de integración. El comportamiento actual es funcional para un operador único — priorizar después de los bugs de a11y más simples.

---

## Grupo 3 — Accesibilidad

### 🟡 VS-11 · Input URL de `AnalyzePage` sin `<label>`

**Archivo**: [`frontend/src/pages/AnalyzePage.tsx:130-138`](../frontend/src/pages/AnalyzePage.tsx)

**Problema**: El input `type="url"` solo tiene `placeholder`. El placeholder desaparece al escribir y los lectores de pantalla no lo anuncian como label del campo.

```diff
+<label htmlFor="analyze-url" className="sr-only">
+  URL del artículo a analizar
+</label>
 <input
+  id="analyze-url"
   type="url"
   ...
 />
```

La clase `sr-only` de Tailwind oculta el label visualmente sin sacarlo del árbol de accesibilidad.

---

### 🟡 VS-12 · Skeletons de carga sin `role="status"`

**Archivo**: [`frontend/src/pages/ReportDetailPage.tsx:188-193`](../frontend/src/pages/ReportDetailPage.tsx)

**Problema**: Los `div` animados que indican carga no tienen semántica. Un lector de pantalla no anuncia que hay contenido cargando.

```diff
-<div className="space-y-2 rounded-xl border p-[22px]" ...>
+<div role="status" aria-label="Cargando reporte..." className="space-y-2 rounded-xl border p-[22px]" ...>
```

---

### 🟡 VS-13 · Área scrolleable del cuerpo del artículo sin `tabindex`

**Archivo**: [`frontend/src/components/AnalysisCard.tsx:271`](../frontend/src/components/AnalysisCard.tsx)

**Problema**: El `div` con `overflow-auto` + `max-h-[230px]` no es alcanzable con Tab — un usuario de teclado no puede scrollear el cuerpo del artículo.

```diff
-<div className="max-h-[230px] overflow-auto rounded-[9px] border ..." ...>
+<div tabIndex={0} className="max-h-[230px] overflow-auto rounded-[9px] border ..." ...>
```

---

### 🟡 VS-14 · Header colapsable de `AnalyzeProgress` no es interactuable por teclado

**Archivo**: [`frontend/src/components/AnalyzeProgress.tsx:44-65`](../frontend/src/components/AnalyzeProgress.tsx)

**Problema**: El header usa `<div onClick>` en vez de `<button>`. No es alcanzable con Tab, no responde a Enter/Space, y no comunica su estado expandido/colapsado.

```diff
-<div
-  onClick={() => setExpanded((v) => !v)}
-  className="flex cursor-pointer select-none ..."
+<button
+  type="button"
+  aria-expanded={expanded}
+  onClick={() => setExpanded((v) => !v)}
+  className="flex w-full cursor-pointer select-none ..."
```

`aria-expanded` anuncia al lector de pantalla si el panel está abierto o cerrado.

---

## Grupo 4 — UX / Nice-to-have

### 🟢 VS-15 · `ReportDetailPage`: pantalla en blanco cuando `id` no es un número válido

**Archivo**: [`frontend/src/pages/ReportDetailPage.tsx:44-45`](../frontend/src/pages/ReportDetailPage.tsx)

**Problema**: Navegando a `/reports/abc`, `Number("abc") === NaN`, la query queda `disabled`, y la página muestra una pantalla completamente vacía sin mensaje de error.

```tsx
if (!Number.isFinite(id)) {
  return (
    <div role="alert" className="odin-glass flex flex-col items-center gap-3 rounded-xl border p-10 text-center">
      <p className="text-[15px] font-semibold">Reporte no encontrado</p>
      <p className="text-[13px]" style={{ color: "var(--muted-foreground)" }}>
        El identificador en la URL no es válido.
      </p>
    </div>
  )
}
```

---

### 🟢 VS-16 · No hay feedback positivo al guardar un análisis exitosamente

**Archivo**: [`frontend/src/pages/AnalyzePage.tsx:69-79`](../frontend/src/pages/AnalyzePage.tsx)

**Problema**: Tras un guardado exitoso, los botones desaparecen y el badge cambia de "Vista previa" a "Guardado en el archivo". Para un operador que procesa decenas de artículos al día, este feedback sutil puede pasar desapercibido.

**Opción A** (mínima): transición CSS más pronunciada en el badge de éxito con `animation: odinIn`.
**Opción B**: sistema de toasts tipo `DialogProvider` — un `ToastProvider` que exponga `useToast()` y muestre notificaciones efímeras desde cualquier mutación.

---

### 🟢 VS-17 · `<title>` genérico — todos los tabs del browser dicen "ODIN"

**Archivo**: [`frontend/index.html:7`](../frontend/index.html)

**Problema**: Con una sola instancia no importa. Con staging + prod + local abiertas simultáneamente, es imposible distinguir las pestañas del browser.

**Fix mínimo**: actualizar `document.title` en cada página con `useEffect`, o usar el mecanismo de `handle` de react-router v7 para declarar títulos por ruta de forma centralizada.

---

## Resumen de PRs sugeridos

| PR | Issues | Esfuerzo estimado |
|----|--------|-------------------|
| `fix/html-basics` | VS-01 | 5 min |
| `fix/nav-links` | VS-02 | 30 min |
| `refactor/error-helpers` | VS-04, VS-05 | 1 h |
| `fix/a11y-pass-1` | VS-03, VS-11, VS-12, VS-13, VS-14 | 2 h |
| `refactor/theme-tokens` | VS-06 | 3–4 h (incremental) |
| `refactor/layout-username` | VS-07 | 20 min |
| `refactor/version-define` | VS-08 | 20 min |
| `fix/article-id-type` | VS-09 | 30 min |
| `fix/empty-states` | VS-15 | 20 min |
| `feat/save-feedback` | VS-16 | 1–2 h |
| `feat/dialog-native` | VS-10 | 3–4 h + tests |

> **Orden recomendado**: empezar por `fix/html-basics` (trivial, impacto inmediato) y `fix/nav-links` (bug real de UX con cero riesgo de regresión). El refactor de tokens (`VS-06`) tiene el mayor payoff a largo plazo pero es el más laborioso — hacerlo en pases por componente, no todo de golpe.
