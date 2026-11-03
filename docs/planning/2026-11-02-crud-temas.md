# Plan: CRUD de Temas (ver, crear, editar, activar/desactivar) — versión TDD

## Context

El módulo `/topics` hoy es de solo lectura en el frontend, aunque el backend ya tiene casi todo el CRUD (`POST/PUT/DELETE /api/topics`, baja lógica, árbol jerárquico, caché del clasificador). Se hace para que un usuario administre el catálogo desde la UI sin tocar la base de datos. El cliente aún no envió su lista de temas (los 7 de `seed_topics.py` son de prueba), así que el CRUD no asume estructura: padre opcional, funciona plano o jerárquico.

**Alcance (aprobado):** listar en árbol, crear (padre opcional), editar nombre/descripción, activar/desactivar, borrar.
**Fuera de alcance:** ver sección final.

**Reglas del repo (CLAUDE.md):** trabajar en la rama actual sin branches/worktrees; **no hacer commits**; no tocar los ~25 archivos ya modificados del rediseño salvo los que este plan nombra; **no llamar a la API de Gemini** (usar `LocalAnalyzer`).

## Entorno de pruebas (detectado del repo)

| Capa | Framework | Comando base | Ejecutar desde |
|---|---|---|---|
| Backend | pytest (`pyproject.toml`: `testpaths=["tests"]`, `addopts="-q"`) con fixtures `api_client` y `sqlite_sessionmaker` | `python -m pytest <ruta> -q` | `C:\ODIN` |
| Frontend | vitest + testing-library + userEvent (`npm test` = `vitest run`) | `npx vitest run <ruta>` | `C:\ODIN\frontend` |
| Tipos | `tsc` | `npx tsc --noEmit` | `C:\ODIN\frontend` |
| Lint | oxlint | `npm run lint` | `C:\ODIN\frontend` |

Notas: las pruebas de API usan SQLite en memoria; **no hay `PRAGMA foreign_keys=ON`** en `src/`, así que los `ondelete="CASCADE"` no se aplican en tests (relevante en T-B9).

## Hallazgos que condicionan el diseño

- `TopicNode` (`src/odin/api/schemas.py:648`) no trae `is_active`, `description` ni `display_order` → el frontend no puede atenuar inactivos ni precargar la edición.
- `TopicPayload.slug` es obligatorio (`schemas.py:663`) pero el usuario solo escribe el nombre → autogenerar en backend (opcional en el payload; si viene, se respeta).
- `delete_topic` (`topic_service.py:229`) devuelve 204 tanto si desactiva como si borra, y decide por `ArticleTopic` directos o **cualquier** hijo (incluso inactivo). El árbol sin "Incluir inactivos" no muestra hijos inactivos → la UI no puede deducir la rama con `children.length`. Ver «Cambios respecto al plan original».
- `get_tree` (`topic_service.py:117-125`): hijo activo de padre inactivo sale como raíz. Intencional; se conserva.
- `update_topic` ignora `description=None` (solo actualiza si `is not None`); borrar el texto desde la UI envía `""`.
- No existe modal con formulario (`lib/dialog.tsx` solo tiene `useConfirm`) → alta y edición **inline**, como `AliasManager.tsx`.
- `ExpandableRow` pone `aria-label` fijo "Ver artículos de …"; las acciones nuevas hacen `stopPropagation`.
- `api-types.ts` es generado: `cd frontend && npm run generate:types`.

## Plantillas a copiar (no reinventar)

- Backend: `topic_service.py`; tests en `tests/api/test_api_topics.py` (helper `_h()` con `create_token("tester")`, fixtures `api_client`/`sqlite_sessionmaker`).
- Frontend: `components/AliasManager.tsx` (edición inline, switch `role="switch"`, `useConfirm({danger:true})`, `err instanceof OdinApiError ? err.message : fallback`), `lib/queries/aliases.ts`, `AliasManager.test.tsx`.

## Cambios respecto al plan original

| # | Cambio | Razón |
|---|---|---|
| C1 | Se añade `child_count` (todos los hijos, incluidos inactivos) a `TopicNode` (T-B7) y la UI lo usa junto con `article_count` para el texto del confirm de borrar. Se mantiene DELETE → 204. | El criterio original `children.length` miente cuando hay hijos inactivos ocultos; el backend los cuenta. Evita cambiar el contrato del endpoint. |
| C2 | Nueva tarea T-B9: borrar un tema vacío no deja alias huérfanos. | En SQLite de tests no se aplica el CASCADE; si falla, es un bug latente real (borrar alias explícitamente en `delete_topic`). |
| C3 | Nueva tarea T-B12: `description` vacía se normaliza a `NULL`. | Evita dos "vacíos" distintos (`""` y `NULL`). |
| C4 | Nueva tarea T-B11: test de espía de `invalidate_cache()` en cada mutación. | El plan original lo pedía como verificación; ahora es una tarea con test propio. |
| C5 | A2 se divide en 4 tareas (derivado, sufijo, vacío→422, explícito/409). A4 se divide en tareas por comportamiento. | «Cada tarea con un solo comportamiento». |
| C6 | Mensaje de 422 explícito: "El nombre debe contener letras o números." | `slugify("***")==""` daba un 422 opaco. |
| C7 | Se añaden prerrequisitos de línea base (P1–P3). | El plan original ya advertía de `get_catalog()` con caché fría; ahora es compuerta ejecutable. |
| C8 | Se organiza en 4 paquetes con checklist; el orden A→F se conserva. | Cada paquete cabe en una sesión. |

Sin cambios: alcance, reglas de slug, alta/edición inline, guardarraíles de diseño, `require_auth`.

## Progreso

**Paquete 1 — Backend (dependencia de todo lo demás)**
- [ ] T-B1 `slugify`
- [ ] T-B2 POST sin slug deriva slug del nombre
- [ ] T-B3 Colisión de slug derivado → sufijo `-2`
- [ ] T-B4 Nombre sin alfanuméricos → 422
- [ ] T-B5 Slug explícito se respeta / choque → 409
- [ ] T-B6 `TopicNode` expone `is_active`, `description`, `display_order`
- [ ] T-B7 `TopicNode.child_count`
- [ ] T-B8 PUT: renombrar, redescribir, reactivar, errores
- [ ] T-B9 DELETE: baja lógica vs borrado duro (+ alias huérfanos)
- [ ] T-B10 POST padre inexistente 404 · mutaciones sin token 401
- [ ] T-B11 `invalidate_cache()` tras cada mutación
- [ ] T-B12 `description` vacía → `NULL`
- [ ] T-B13 Compuerta Parte A (suite completa)

**Paquete 2 — Frontend: contratos y datos**
- [ ] T-F1 Regenerar tipos (sin TDD)
- [ ] T-F2 Cliente API `createTopic/updateTopic/deleteTopic`
- [ ] T-F3 `flattenTopicTree` con campos nuevos
- [ ] T-F4 Hooks de mutación

**Paquete 3 — Frontend: componentes**
- [ ] T-F5 `NewTopicForm`: valida nombre vacío
- [ ] T-F6 `NewTopicForm`: payload con y sin padre
- [ ] T-F7 `NewTopicForm`: error del servidor inline
- [ ] T-F8 `TopicRowCells` vista: atenuado de inactivos
- [ ] T-F9 `TopicRowCells`: switch activa/desactiva
- [ ] T-F10 `TopicRowCells`: edición guarda
- [ ] T-F11 `TopicRowCells`: Escape cancela
- [ ] T-F12 `TopicRowCells`: borrar con confirmación
- [ ] T-F13 `TopicRowCells`: acciones no expanden la fila

**Paquete 4 — Integración y cierre**
- [ ] T-F14 `TopicsPage`: columnas y celdas nuevas
- [ ] T-F15 `TopicsPage`: estado vacío con CTA
- [ ] T-F16 Compuerta frontend (guardarraíles + tsc + lint)
- [ ] T-E1 Verificación E2E manual
- [ ] T-E2 Cierre: bóveda Obsidian

## Prerrequisitos

- [ ] **P1 — Línea base backend:** `python -m pytest tests/api/test_api_topics.py tests/api/test_api_topics_counts.py tests/api/test_api_topics_wiring.py tests/analysis tests/core/test_pipeline_topics.py -q` en verde **antes** de tocar nada. Si falla (p. ej. por `get_catalog()` con caché fría, ver `plans/2026-09-08-catalogo-temas.md` tareas 6-8), **parar y avisar al usuario**.
- [ ] **P2 — Línea base frontend:** `npx vitest run` en verde (incluye los 4 tests de guardarraíles). Anotar los que ya fallen para no atribuirlos al cambio.
- [ ] **P3 — Árbol de trabajo:** `git status` / `git diff --stat`; confirmar que `TopicsPage.tsx`, `topic-tree.ts`, `queries/topics.ts`, `odin-api.ts`, `schemas.py`, `topic_service.py`, `text_norm.py` no tienen cambios sin commitear del rediseño; si los tienen, avisar antes de editar.
- [ ] **P4 — Leer antes de escribir:** `components/ExpandableRow.tsx`, `pages/TopicsPage.tsx`, `pages/TopicsPage.test.tsx`, `AliasManager.tsx` + su test, `lib/queries/aliases.ts`.

Regla de cada tarea: escribir el test → **verlo fallar por la razón correcta** (citar el mensaje) → implementar lo mínimo → verde → marcar checkbox. Los tests de caracterización nacen verdes: decirlo explícitamente, no fingir rojo; si alguno falla es un bug real y se arregla con ciclo rojo/verde. Sin commits.

---

# PAQUETE 1 — Backend

## T-B1 `slugify`
- **Objetivo:** función pura que convierte un nombre en slug URL-seguro.
- **Criterios:** `slugify("Política y Gobierno")=="politica-y-gobierno"`; símbolos/espacios múltiples colapsan a un único `-` sin guiones en los extremos; `slugify("***")==""`; `slugify("a-b")=="a-b"`.
- **Test PRIMERO:** `tests/analysis/test_text_norm.py` (crear), nivel unidad, `test_slugify_*` (parametrizado con los 4 casos). *Implementar:* `slugify` en `text_norm.py` junto a `norm_key`, reutilizando `strip_accents`; regex `[^a-z0-9]+` → `-`, `strip("-")`.
- **Archivos:** `src/odin/analysis/text_norm.py`, `tests/analysis/test_text_norm.py`.
- **Verificación:** `python -m pytest tests/analysis/test_text_norm.py -q`
- **Hecho:** test pasa + checkbox.
- **Riesgos:** `norm_key` convierte `-` en espacio; el caso `"a-b"` lo cubre.

## T-B2 POST sin slug deriva el slug del nombre
- **Objetivo:** crear tema enviando solo `name`.
- **Criterios:** `POST /api/topics {"name":"Política y Gobierno"}` → 201 con `slug=="politica-y-gobierno"`; el schema OpenAPI marca `slug` como no requerido.
- **Test PRIMERO:** `tests/api/test_api_topics.py::test_create_without_slug_derives_it`, integración (`api_client`). Falla hoy con 422 (campo requerido). *Implementar:* `TopicPayload.slug: str | None = Field(default=None, max_length=160)`; en `create_topic`, `slug = (payload.slug or "").strip() or slugify(name)`.
- **Archivos:** `schemas.py`, `topic_service.py`, `test_api_topics.py`.
- **Verificación:** `python -m pytest tests/api/test_api_topics.py -q -k derives`
- **Riesgos:** regenerar tipos en T-F1; ningún cliente existente rompe (el campo pasa a opcional).

## T-B3 Colisión de slug derivado → sufijo `-2`
- **Objetivo:** dos temas con el mismo slug derivado coexisten.
- **Criterios:** crear "Salud" raíz y "Salud" bajo otro padre → slugs `salud` y `salud-2`; un tercero → `salud-3`.
- **Test PRIMERO:** `test_derived_slug_collision_gets_suffix` (integración). Falla hoy con 409. *Implementar:* bucle acotado (p. ej. hasta 50) probando `-2`, `-3`…; si se agota → 409.
- **Archivos:** `topic_service.py`, `test_api_topics.py`.
- **Verificación:** `python -m pytest tests/api/test_api_topics.py -q -k suffix`
- **Riesgos:** carrera entre peticiones concurrentes (el slug no es UNIQUE en BD); aceptado, fuera de alcance.

## T-B4 Nombre sin alfanuméricos → 422
- **Objetivo:** rechazar nombres que no producen slug.
- **Criterios:** `{"name":"***"}` → 422 con detalle "El nombre debe contener letras o números."; no se crea fila.
- **Test PRIMERO:** `test_name_without_alphanumerics_is_422` (integración; también comprueba que `GET /api/topics?include_inactive=true` no crece). *Implementar:* si `slugify(name)==""` y no hay slug explícito → `HTTPException(422, …)`.
- **Archivos:** `topic_service.py`, `test_api_topics.py`.
- **Verificación:** `python -m pytest tests/api/test_api_topics.py -q -k alphanumerics`

## T-B5 Slug explícito se respeta; choque explícito → 409 (caracterización)
- **Objetivo:** no romper el comportamiento previo.
- **Criterios:** POST con `slug:"mi-slug"` devuelve ese slug; repetirlo → 409 "El slug 'mi-slug' ya está en uso." (sin sufijo automático).
- **Test PRIMERO:** `test_explicit_slug_respected_and_clash_409` (integración). Nace verde si T-B2/B3 no regresionan: **declararlo**.
- **Verificación:** `python -m pytest tests/api/test_api_topics.py -q -k explicit`

## T-B6 `TopicNode` expone `is_active`, `description`, `display_order`
- **Objetivo:** el árbol trae lo necesario para atenuar y precargar edición.
- **Criterios:** con `include_inactive=true` un tema desactivado trae `is_active:false`, `description`, `display_order`; sin el flag el inactivo no aparece; `aliases` sigue siendo `list[str]`.
- **Test PRIMERO:** `test_tree_exposes_state_fields` (integración, `GET /api/topics/tree`). Falla por `KeyError`. *Implementar:* campos con defaults `True`, `None`, `0` en `TopicNode`; poblarlos en `get_tree`.
- **Archivos:** `schemas.py`, `topic_service.py`, `test_api_topics.py`.
- **Verificación:** `python -m pytest tests/api/test_api_topics.py -q -k state_fields`

## T-B7 `TopicNode.child_count`
- **Objetivo:** que la UI sepa si el borrado será baja lógica aunque haya hijos ocultos (C1).
- **Criterios:** padre con un hijo inactivo → `GET /tree` (sin `include_inactive`) devuelve `child_count==1` y `children==[]`; hoja → `0`.
- **Test PRIMERO:** `test_tree_child_count_includes_inactive_children` (integración). *Implementar:* contar hijos por `parent_id` sobre **todas** las filas (query aparte sin filtro de activo), campo `child_count: int = 0`.
- **Archivos:** `schemas.py`, `topic_service.py`, `test_api_topics.py`.
- **Verificación:** `python -m pytest tests/api/test_api_topics.py -q -k child_count`

## T-B8 PUT: renombrar, redescribir, reactivar, errores (caracterización)
- **Objetivo:** fijar el contrato de edición.
- **Criterios:** PUT cambia nombre y descripción; nombre vacío → 422; nombre duplicado entre hermanos → 409; id inexistente → 404; `is_active` false→true reactiva.
- **Test PRIMERO:** cinco tests pequeños `test_put_*` (integración). Nacen verdes; **declararlo**. Un fallo = bug real → ciclo rojo/verde.
- **Verificación:** `python -m pytest tests/api/test_api_topics.py -q -k put_`
- **Riesgos:** reactivar un hijo con padre inactivo lo deja como raíz (intencional, no se propaga; solo se prueba que no falla).

## T-B9 DELETE: baja lógica vs borrado duro + alias huérfanos
- **Objetivo:** fijar la regla de borrado y detectar alias huérfanos (C2).
- **Criterios:** con artículos **o** con hijos (incluso inactivos) → 204 y sigue en `include_inactive` con `is_active:false`; tema vacío → 204 y desaparece **y no quedan filas en `topic_aliases`**; id inexistente → 404.
- **Test PRIMERO:** `test_delete_*` (integración con `sqlite_sessionmaker`). Los de baja lógica nacen verdes (declararlo). `test_delete_empty_topic_removes_its_aliases` puede nacer **rojo** (SQLite sin FK): si falla, implementar `session.query(TopicAlias).filter_by(topic_id=…).delete()` antes de `session.delete(row)`.
- **Archivos:** `topic_service.py`, `test_api_topics.py`.
- **Verificación:** `python -m pytest tests/api/test_api_topics.py -q -k delete`

## T-B10 POST padre inexistente → 404 · mutaciones sin token → 401 (caracterización)
- **Criterios:** `parent_id=99999` → 404; POST/PUT/DELETE sin `Authorization` → 401.
- **Test PRIMERO:** `test_create_unknown_parent_404`, `test_mutations_require_auth` (parametrizado por método). Nacen verdes; declararlo.
- **Verificación:** `python -m pytest tests/api/test_api_topics.py -q -k "parent_404 or require_auth"`

## T-B11 `invalidate_cache()` tras cada mutación (C4)
- **Objetivo:** el clasificador refleja el cambio en el siguiente request.
- **Criterios:** tras POST, PUT y DELETE exitosos `topic_store.invalidate_cache` se llamó una vez; tras un error (404/409) no.
- **Test PRIMERO:** `test_mutations_invalidate_catalog_cache` (integración, `monkeypatch` de `odin.db.topics.invalidate_cache` con contador). Nace verde; declararlo.
- **Verificación:** `python -m pytest tests/api/test_api_topics.py -q -k invalidate`

## T-B12 `description` vacía → `NULL` (C3)
- **Criterios:** PUT con `description:""` guarda `NULL` (respuesta `description is None`); POST con `""` igual.
- **Test PRIMERO:** `test_blank_description_stored_as_null` (integración). Falla hoy (devuelve `""`). *Implementar:* `description = (value or "").strip() or None` en create y update (cuando `description is not None`).
- **Verificación:** `python -m pytest tests/api/test_api_topics.py -q -k blank_description`

## T-B13 Compuerta Parte A
- **Objetivo:** nada se rompió.
- **Criterios:** suite del paquete y suite completa en verde.
- **Verificación:** `python -m pytest tests/api/test_api_topics.py tests/api/test_api_topics_counts.py tests/api/test_api_topics_wiring.py tests/analysis tests/core/test_pipeline_topics.py -q` y luego `python -m pytest -q`.
- **Riesgos:** fallos previos a P1 no se atribuyen al cambio.

---

# PAQUETE 2 — Frontend: contratos y datos
*Depende de: Paquete 1 completo (T-F1 necesita los schemas finales).*

## T-F1 Regenerar tipos (sin TDD)
- **Objetivo:** `api-types.ts` refleja el backend nuevo.
- **Criterios:** `TopicNode` incluye `is_active`, `description`, `display_order`, `child_count`; `TopicPayload.slug` es opcional; `api-types.ts` no se edita a mano.
- **Verificación (en lugar de test):** `npm run generate:types` + `Select-String -Path src/lib/api-types.ts -Pattern "child_count"` + `npx tsc --noEmit` (puede mostrar errores en consumidores; se resuelven en T-F3).
- **Riesgos:** `generate:types` descarga `openapi-typescript` vía `npx` (comando ya definido en `package.json`); si no hay red, avisar, no editar el archivo a mano.

## T-F2 Cliente API
- **Objetivo:** `createTopic`, `updateTopic`, `deleteTopic`.
- **Criterios:** cada una llama al método/URL correctos (`POST /api/topics`, `PUT /api/topics/{id}`, `DELETE /api/topics/{id}`) con body JSON y token; un 409 lanza `OdinApiError` con el `detail`.
- **Test PRIMERO:** en el test existente de `odin-api` (localizarlo con Glob; si no existe, crear `odin-api.topics.test.ts`), nivel unidad con `fetch` mockeado: `createTopic envía POST con payload`, `deleteTopic resuelve en 204`, `updateTopic propaga OdinApiError`. *Implementar:* funciones junto a `getTopicTree` (~línea 403) imitando alias (~440-460); tipos desde `components["schemas"]`.
- **Archivos:** `src/lib/odin-api.ts`, su test.
- **Verificación:** `npx vitest run src/lib/odin-api`

## T-F3 `flattenTopicTree` con campos nuevos
- **Criterios:** cada `TopicRow` trae `parent_id`, `is_active`, `description`, `display_order`, `child_count`, `has_children`; el orden y `depth` actuales no cambian.
- **Test PRIMERO:** `src/lib/topic-tree.test.ts` (existe), unidad: `incluye los campos de estado y has_children`. Falla por `undefined`. *Implementar:* extender `TopicRow` y la función.
- **Verificación:** `npx vitest run src/lib/topic-tree.test.ts`

## T-F4 Hooks de mutación
- **Criterios:** tras `useCreateTopic`/`useUpdateTopic`/`useDeleteTopic` exitosos se invalida `topicKeys.all` (se vuelve a pedir el árbol); un error no invalida y se expone en `error`.
- **Test PRIMERO:** `src/lib/queries/topics.test.tsx` (crear), integración con `QueryClientProvider` y `odin-api` mockeado: `invalida el árbol tras crear`, `…tras actualizar`, `…tras borrar`, `no invalida si falla`. *Implementar:* hooks en `queries/topics.ts` (patrón de `aliases.ts`).
- **Verificación:** `npx vitest run src/lib/queries/topics.test.tsx`

---

# PAQUETE 3 — Frontend: componentes (`src/components/topics/`)
*Depende de: Paquete 2 (T-F2…T-F4). Cada `.test.tsx` se escribe antes que su componente.*

**Guardarraíles (los tests del repo los hacen cumplir, ver T-F16):** solo tokens CSS (`var(--surface)`, `--border`, `--faint`, `--pos`, `--neg`, `--primary`, `--accent-soft`…), prohibido hex/rgb literales y vidrio/blur; radios: inputs/botones `rounded-lg`, chips `rounded-md`, tarjetas `rounded-xl`, badge `rounded-full`; tarjeta `rounded-xl border bg-card` + `boxShadow: var(--shadow-sm)`; switch activo `--pos`, inactivo `--surface-3`, peligro `--neg`; español directo en JSX; reutilizar `ui/button`, `ui/badge`, `ui/skeleton`, `ui/alert`; `aria-label` en todo icono, `focus-visible:ring-2 ring-ring`, `role="switch"` + `aria-checked`.

## T-F5 `NewTopicForm`: valida nombre vacío
- **Criterios:** botón "Nuevo tema" despliega el formulario; enviar con nombre vacío/espacios muestra "El nombre es obligatorio" y **no** llama a la API.
- **Test PRIMERO:** `NewTopicForm.test.tsx` · unidad/componente: `no envía con nombre vacío`. *Implementar:* tarjeta plegable con campos Nombre, Descripción, Padre.
- **Verificación:** `npx vitest run src/components/topics/NewTopicForm.test.tsx`

## T-F6 `NewTopicForm`: payload con y sin padre
- **Criterios:** sin padre envía `{name, description, parent_id: null}` (sin `slug`); con padre elegido envía su id; el `<select>` lista "Sin padre (raíz)" + solo temas activos, con sangría por `depth`; al éxito limpia y cierra.
- **Test PRIMERO:** `envía payload sin slug y sin padre`, `envía parent_id al elegir padre`, `limpia y cierra al éxito`, `no lista temas inactivos como padre`. *Implementar:* submit con `useCreateTopic`.
- **Verificación:** igual que T-F5.

## T-F7 `NewTopicForm`: error del servidor inline
- **Criterios:** un 409/404/422 muestra `OdinApiError.message` junto al formulario (sin cerrar); durante `pending` el botón queda deshabilitado.
- **Test PRIMERO:** `muestra el mensaje 409`, `deshabilita mientras envía`. *Implementar:* estado de error y `isPending`.
- **Verificación:** igual que T-F5.

## T-F8 `TopicRowCells` vista: atenuado de inactivos
- **Criterios:** muestra nombre (con `paddingLeft`/`data-depth`), descripción en `--faint`, `Badge secondary` con `article_count`; si `is_active=false`, las celdas de texto llevan `opacity-45` y las acciones **no**.
- **Test PRIMERO:** `TopicRowCells.test.tsx`: `renderiza nombre, descripción y conteo`, `atenúa solo el texto cuando está inactivo`. *Implementar:* modo vista.
- **Verificación:** `npx vitest run src/components/topics/TopicRowCells.test.tsx`

## T-F9 `TopicRowCells`: switch activa/desactiva
- **Criterios:** switch `role="switch"` con `aria-label` "Desactivar tema X"/"Activar tema X" y `aria-checked`; clic llama `updateTopic(id, {is_active: !actual})`.
- **Test PRIMERO:** `el switch envía is_active invertido` (ambos sentidos), `el aria-label cambia con el estado`.
- **Verificación:** igual que T-F8.

## T-F10 `TopicRowCells`: edición guarda
- **Criterios:** Editar (Pencil, `aria-label`) muestra inputs precargados; Check o Enter envía `{name, description}`; error inline con el mensaje del servidor; nombre vacío no envía.
- **Test PRIMERO:** `guardar envía name y description`, `Enter guarda`, `nombre vacío no llama`, `muestra error 409`.
- **Verificación:** igual que T-F8.

## T-F11 `TopicRowCells`: Escape cancela
- **Criterios:** Escape o X vuelve a modo vista descartando cambios sin llamar a la API.
- **Test PRIMERO:** `Escape cancela sin llamar`, `X cancela`.
- **Verificación:** igual que T-F8.

## T-F12 `TopicRowCells`: borrar con confirmación
- **Criterios:** Borrar (Trash2, `aria-label`) abre `useConfirm({danger:true})`; texto "se **desactivará**" si `article_count>0 || child_count>0`, si no "se **eliminará** definitivamente"; cancelar no llama a la API; confirmar llama `deleteTopic(id)`.
- **Test PRIMERO:** `confirm distinto con artículos`, `confirm distinto con child_count aunque children esté vacío` (caso C1), `cancelar no borra`, `confirmar borra`.
- **Verificación:** igual que T-F8.

## T-F13 `TopicRowCells`: acciones no expanden la fila
- **Criterios:** clic en switch, Editar, Borrar, Guardar y Cancelar no dispara el `onClick` del contenedor (`ExpandableRow`).
- **Test PRIMERO:** `las acciones no propagan el click` (padre con spy). *Implementar:* `e.stopPropagation()` en todos los handlers (y en keydown Enter/Space de los controles).
- **Verificación:** igual que T-F8.

---

# PAQUETE 4 — Integración y cierre
*Depende de: Paquete 3.*

## T-F14 `TopicsPage`: columnas y celdas nuevas
- **Criterios:** tabla con 4 columnas (`Tema`, `Artículos`, `Estado`, acciones); `NewTopicForm` sobre la tabla; buscador, "Incluir inactivos", skeleton y `Alert` de error se conservan; el panel expandible de artículos no cambia.
- **Test PRIMERO:** actualizar `pages/TopicsPage.test.tsx` (que mockea `@/lib/queries/topics`): añadir mocks de las tres mutaciones y los campos nuevos del fixture; nuevos casos `muestra el formulario de alta`, `renderiza las 4 columnas`, `un tema inactivo se ve atenuado con "Incluir inactivos"`. Falla antes de implementar. *Implementar:* actualizar `COLUMNS`, reemplazar celdas inline por `TopicRowCells`.
- **Archivos:** `pages/TopicsPage.tsx`, su test.
- **Verificación:** `npx vitest run src/pages/TopicsPage.test.tsx`
- **Riesgos:** leer `ExpandableRow` primero (P4).

## T-F15 `TopicsPage`: estado vacío con CTA
- **Criterios:** sin temas y sin búsqueda activa aparece "Crea el primer tema" que abre el formulario; con búsqueda sin resultados se mantiene el mensaje actual sin CTA.
- **Test PRIMERO:** `muestra CTA cuando no hay temas`, `no muestra CTA al buscar`.
- **Verificación:** igual que T-F14.

## T-F16 Compuerta frontend
- **Criterios:** suite completa (con guardarraíles `no-hardcoded-colors`, `flat-surfaces`, `no-legacy-glass`, `css-tokens`), `tsc` y lint limpios.
- **Verificación:** `npx vitest run` · `npx tsc --noEmit` · `npm run lint`.
- **Riesgos:** fallos previos anotados en P2 no se atribuyen.

## T-E1 Verificación E2E manual
Backend + frontend con la skill `run` (analizador `LocalAnalyzer`, **nunca `--analyzer gemini`**). En el navegador: crear tema raíz y subtema → editar nombre → desactivar (se atenúa; desaparece sin "Incluir inactivos") → reactivar → borrar uno vacío (desaparece) y uno con artículos (queda inactivo). Probar tema claro/oscuro y ancho móvil. Añadir un alias vía API y confirmar en la vista previa de `/api/analyze` que un tema desactivado ya no se sugiere y uno nuevo sí.

## T-E2 Cierre
Actualizar la nota del proyecto en la bóveda de Obsidian (`Proyectos/`) y añadir entrada a `Bitácora/2026-11-02.md` (decisión: CRUD con padre opcional, slug autogenerado, `child_count`, alias en etapa 2). Sin secretos.

---

## Tareas sin TDD: verificación sustituta

| Tarea | Por qué no es TDD | Verificación |
|---|---|---|
| T-F1 Tipos generados | Salida de herramienta, no lógica | `grep` de los campos nuevos + `tsc --noEmit` |
| Estilo/guardarraíles visuales | Apariencia | Tests de guardarraíles existentes (T-F16) + revisión visual en T-E1 (claro/oscuro/móvil) |
| T-E1 Flujo completo | Integración real navegador↔API | Checklist manual paso a paso |
| T-E2 Bóveda | Documentación | Revisión de la nota y la bitácora |
| Migraciones | **No hay**: ningún cambio de modelo/BD en este plan | — |

## Trazabilidad: requisito → tarea → test

| Requisito | Tarea(s) | Test |
|---|---|---|
| Listar en árbol con estado | T-B6, T-F3, T-F14 | `test_tree_exposes_state_fields`, `incluye los campos de estado…`, `renderiza las 4 columnas` |
| Crear tema, padre opcional | T-B2, T-F5, T-F6 | `test_create_without_slug_derives_it`, `envía payload sin slug y sin padre` |
| Slug autogenerado, único | T-B1, T-B3, T-B4, T-B5 | `test_slugify_*`, `…collision_gets_suffix`, `…without_alphanumerics_is_422`, `…explicit_slug…` |
| Editar nombre/descripción | T-B8, T-B12, T-F10, T-F11 | `test_put_*`, `test_blank_description_stored_as_null`, `guardar envía name y description` |
| Activar/desactivar | T-B8, T-F9 | `test_put_reactivates`, `el switch envía is_active invertido` |
| Borrar (baja lógica vs duro) | T-B7, T-B9, T-F12 | `test_delete_*`, `…child_count_includes_inactive_children`, `confirm distinto con child_count…` |
| Filas inactivas atenuadas | T-B6, T-F8 | `atenúa solo el texto cuando está inactivo` |
| Acciones no expanden fila | T-F13 | `las acciones no propagan el click` |
| Errores visibles al usuario | T-F7, T-F10 | `muestra el mensaje 409` |
| Auth en mutaciones | T-B10 | `test_mutations_require_auth` |
| Clasificador refleja cambios | T-B11, T-E1 | `test_mutations_invalidate_catalog_cache`, E2E paso 3 |
| Sin alias huérfanos | T-B9 | `test_delete_empty_topic_removes_its_aliases` |
| Estado vacío / CTA | T-F15 | `muestra CTA cuando no hay temas` |
| Refresco tras mutar | T-F4 | `invalida el árbol tras …` |
| Cliente API correcto | T-F2 | `createTopic envía POST con payload`, etc. |
| Diseño según guardarraíles | T-F16 | tests `no-hardcoded-colors`, `flat-surfaces`, `no-legacy-glass`, `css-tokens` |
| Cierre documentado | T-E2 | revisión manual |

## Orden de ejecución

P1–P4 → Paquete 1 (T-B1 → T-B13) → Paquete 2 (T-F1 → T-F4) → Paquete 3 (T-F5 → T-F13) → Paquete 4 (T-F14 → T-F16, T-E1, T-E2). Una tarea a la vez, ciclo rojo/verde, sin commits. Un paquete por sesión.

## Fuera de alcance (etapa 2)

Gestión de alias (UI; requeriría exponer `id`/`is_active` por alias y un endpoint para activarlos) · mover de padre · cambiar slug · importación masiva de la lista del cliente · restringir escrituras a admin (se mantiene `require_auth`, igual que `aliases.py`; **pendiente de confirmar con el usuario**, no bloquea) · propagar activación/desactivación a hijos · unicidad de `slug` a nivel de BD.
