import { OdinApiError } from "@/lib/api-error"
import { clearSession, getToken, notifyAuthExpired, setSession } from "@/lib/auth"
import type { components } from "@/lib/api-types"

// Los tipos de forma (Article*, Entity*, CanonicalEntity*, Alias*) salen del
// OpenAPI real de la API (`response_model=` en api.py/auth.py) en vez de
// mantenerse a mano: era la tercera copia del mismo listado de campos, junto
// a los modelos SQLAlchemy y los serializadores de api.py (§9.2 de task.md,
// tarea 25). Para regenerar tras un cambio de schema: `npm run generate:types`.

export type EntityAnalysis = components["schemas"]["EntityMention"]

// Vista previa de POST /api/analyze (aún no guardada, o eco de un artículo ya
// existente): schema separado de ArticleAnalysis/EntityAnalysis porque son
// casos de uso distintos — acá `id`/`body` pueden ser `null`, cosa que nunca
// pasa en un artículo ya persistido (ver api/schemas.py, AnalyzeResult).
export type AnalyzePreviewEntity = components["schemas"]["AnalyzePreviewEntity"]
export type AnalyzeResult = components["schemas"]["AnalyzeResult"]
// Lugar propuesto por el analizador dentro de la vista previa: todavía no es
// un vínculo guardado, por eso no es `ArticleLocality`.
export type SuggestedLocality = components["schemas"]["SuggestedLocality"]

// Enumeraciones fijas del análisis (ver SENTIMENT_VALUES/FRAMING_VALUES/... en
// api.py): el schema las declara como `string` porque los campos ORM son
// `String(...)` sin CHECK constraint, así que se mantienen a mano aquí para
// quien quiera el tipo estrecho al construir un valor.
export type Framing =
  | "crisis_conflicto"
  | "logro_institucional"
  | "negligencia"
  | "crecimiento"
  | "denuncia"
  | "neutro_informativo"

export type HeadlineIntent = "informativo" | "alarmista" | "sensacionalista"
export type LeadOrientation = "social" | "oficialista" | "tecnico"
export type SourceQuality =
  | "citas_directas"
  | "testimonios_anonimos"
  | "datos_duros"
  | "mixtas"
  | "sin_fuentes"

export type ArticleAnalysis = components["schemas"]["ArticleDetail"]

export type SaveArticlePayload = Omit<
  AnalyzeResult,
  | "id"
  | "already_saved"
  | "analyzer_name"
  | "analyzer_model"
  | "analyzer_version"
  | "analysis_schema_version"
  | "analyzed_at"
> & {
  /** Lugares de la noticia, para el alta manual. Viajan en el mismo cuerpo
   *  para que artículo y vínculos entren o fallen juntos. */
  localities?: components["schemas"]["ArticleLocalityPayload"][]
}

export interface ArticleUpdatePayload {
  main_topic?: string | null
  topic_keywords?: string | null
  overall_sentiment?: "POS" | "NEG" | "NEU" | null
  sentiment_score?: number | null
  framing?: Framing | null
  headline_intent?: HeadlineIntent | null
  lead_orientation?: LeadOrientation | null
  dominant_actor?: string | null
  source_quality?: SourceQuality | null
  has_hard_data?: boolean | null
  blamed_actor?: string | null
  credited_actor?: string | null
}

export interface EntityUpdatePayload {
  name?: string
  type?: "PERSON" | "ORG"
  sentiment_toward?: "POS" | "NEG" | "NEU" | null
  sentiment_score?: number | null
  context?: string | null
}

export type ArticleSummary = components["schemas"]["ArticleSummary"]

export type ArticleListResponse = components["schemas"]["ArticleListResponse"]

export type ArticleFilterOptions = components["schemas"]["ArticleFiltersResponse"]

export interface ArticleListParams {
  q?: string
  source?: string
  sentiment?: string
  framing?: string
  headline_intent?: string
  lead_orientation?: string
  source_quality?: string
  has_hard_data?: boolean
  entity?: string
  /** Texto del tema. Coincidencia parcial contra `main_topic`, que es texto
   *  libre mientras no exista el catálogo administrable (R4): escribir
   *  "policía" alcanza "policía nacional" y "policía municipal". */
  topic?: string
  /** Id de un lugar del catálogo. El backend incluye su subárbol: filtrar
   *  por una provincia trae también lo marcado en sus municipios. */
  locality?: number
  date_from?: string
  date_to?: string
  /** Columna por la que ordenar. El backend además acepta "recent"/"oldest"
   *  como alias del contrato anterior, para enlaces ya guardados; el cliente
   *  no los emite, así que no entran en este tipo. */
  sort?: "published_at" | "source" | "analyzed_on"
  order?: "asc" | "desc"
  documentalist?: number
  limit?: number
  offset?: number
}

export type EntityAlias = components["schemas"]["EntityAliasResponse"]

export type AliasPayload = components["schemas"]["AliasPayload"]

export type AliasUpdatePayload = components["schemas"]["AliasUpdatePayload"]

// ── Entidades canónicas ──────────────────────────────────────────────────────

export type CanonicalEntity = components["schemas"]["CanonicalEntityResponse"]

export type CanonicalEntityDetail = components["schemas"]["CanonicalEntityDetailResponse"]

export type CanonicalEntityArticleMention = components["schemas"]["CanonicalEntityArticleMention"]

export type CanonicalEntityListResponse = components["schemas"]["CanonicalEntityListResponse"]

export interface CanonicalEntityListParams {
  q?: string
  type?: "ORG" | "PERSON"
  limit?: number
  offset?: number
}

export type CanonicalEntityUpdatePayload = components["schemas"]["CanonicalEntityUpdatePayload"]

// Re-exportado para no romper a quien ya lo importa desde acá; la clase
// vive en `api-error.ts` (ver el porqué allí).
export { OdinApiError } from "@/lib/api-error"

const BASE = ""

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  return (await requestWithStatus<T>(path, init)).data
}

/** Como `request`, pero devuelve también el código de estado. Existe porque el
 *  alta de reportes distingue 201 (se creó) de 200 (la URL ya estaba), y esa
 *  diferencia no se puede leer del cuerpo. */
async function requestWithStatus<T>(
  path: string,
  init?: RequestInit
): Promise<{ data: T; status: number }> {
  const headers = new Headers(init?.headers)
  const token = getToken()
  if (token) headers.set("Authorization", `Bearer ${token}`)

  const res = await fetch(BASE + path, { ...init, headers })

  // 401 = token ausente, inválido o vencido. Se limpia la sesión y App vuelve
  // al login en vez de dejar la pantalla mostrando un error genérico.
  if (res.status === 401) {
    clearSession()
    notifyAuthExpired()
    const body = await res.json().catch(() => null)
    throw new OdinApiError(body?.detail ?? "La sesión expiró.")
  }

  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new OdinApiError(body?.detail ?? `Error ${res.status} en ${path}.`)
  }
  if (res.status === 204) return { data: undefined as unknown as T, status: res.status }
  return { data: await res.json(), status: res.status }
}

async function postJson<T>(path: string, payload: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
}

async function putJson<T>(path: string, payload: unknown): Promise<T> {
  return request<T>(path, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
}

async function del(path: string): Promise<void> {
  return request<void>(path, { method: "DELETE" })
}

// ── Autenticación ───────────────────────────────────────────────────────────

export type LoginResponse = components["schemas"]["TokenResponse"]

/** Inicia sesión y guarda el token. No pasa por request(): un 401 aquí es una
 *  contraseña equivocada, no una sesión vencida, y no debe disparar el evento
 *  que devuelve la aplicación al login. */
export async function login(username: string, password: string): Promise<LoginResponse> {
  const res = await fetch(`${BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new OdinApiError(body?.detail ?? "No se pudo iniciar sesión.")
  }
  const data: LoginResponse = await res.json()
  setSession(data.access_token, data.username)
  return data
}

export const MIN_PASSWORD_LENGTH = 8

/** Cambia la contraseña y **rota la sesión**.
 *
 *  El portón de cambio obligatorio viaja como claim del JWT, así que el token
 *  con el que se llega aquí sigue cerrando todo lo demás: hay que reemplazarlo
 *  por el que devuelve el servidor o la aplicación queda trabada con la
 *  contraseña ya cambiada. */
export async function changePassword(newPassword: string): Promise<LoginResponse> {
  const data = await request<LoginResponse>("/api/auth/change-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ new_password: newPassword }),
  })
  setSession(data.access_token, data.username)
  return data
}

/** Valida el token guardado al abrir la aplicación. */
export function getMe(): Promise<components["schemas"]["MeResponse"]> {
  return request<components["schemas"]["MeResponse"]>("/api/auth/me")
}

// ── Análisis ────────────────────────────────────────────────────────────────
//
// POST /api/analyze ya no bloquea hasta que termine la descarga+NLP (podía
// tardar hasta ~60s, §3.1 de task.md): si la URL es nueva, encola un job y
// responde 202 de inmediato; `analyzeUrl` hace el polling de
// GET /api/jobs/{job_id} por dentro, así que quien la llama sigue recibiendo
// una promesa que resuelve en `ArticleDetail`, igual que antes. `onStatus` es
// opcional, para que la UI muestre progreso real en vez de un spinner ciego —
// recibe también `stage` (fetching/analyzing/canonicalizing, ver ANALYZE_STAGES
// en services/analyze_service.py) para detallar en qué parte del pipeline va.

export type JobStatus = components["schemas"]["JobResponse"]["status"]
export type AnalyzeStage = NonNullable<components["schemas"]["JobResponse"]["stage"]>

const JOB_POLL_INTERVAL_MS = 1500
// 240s y no 120s: el backend acota cada llamada al motor de análisis (ver
// _REQUEST_TIMEOUT_SECONDS en analysis/groq_analyzer.py y _REQUEST_TIMEOUT_MS en
// analysis/gemini_analyzer.py), pero el peor caso encadena Groq + su reintento
// + el fallback a Gemini y puede acercarse a los 150s. Rendirse antes no
// cancela nada: el job sigue corriendo en el servidor y el resultado —que en
// ese camino ya se pagó— quedaba guardado sin que nadie lo llegara a ver.
const JOB_POLL_TIMEOUT_MS = 240_000

// Con la pestaña oculta, los polls de jobs en curso (análisis, scraper) se
// espacian para no gastar CPU/red/batería en segundo plano — el job del
// backend sigue corriendo igual, solo se revisa con menos frecuencia. Apenas
// la pestaña vuelve a estar visible se corta la espera y se refresca al toque
// en vez de dejar el último estado mostrado quedarse desactualizado.
const HIDDEN_POLL_MULTIPLIER = 4

function pollDelay(ms: number): Promise<void> {
  const hidden = typeof document !== "undefined" && document.visibilityState === "hidden"
  const delay = hidden ? ms * HIDDEN_POLL_MULTIPLIER : ms
  return new Promise((resolve) => {
    const timer = setTimeout(finish, delay)
    function finish() {
      document.removeEventListener("visibilitychange", onVisible)
      resolve()
    }
    function onVisible() {
      if (document.visibilityState !== "hidden") {
        clearTimeout(timer)
        finish()
      }
    }
    if (hidden) document.addEventListener("visibilitychange", onVisible)
  })
}

async function pollJob(
  jobId: string,
  onStatus?: (status: JobStatus, stage: AnalyzeStage | null) => void
): Promise<AnalyzeResult> {
  const deadline = Date.now() + JOB_POLL_TIMEOUT_MS
  for (;;) {
    const job = await request<components["schemas"]["JobResponse"]>(`/api/jobs/${jobId}`)
    onStatus?.(job.status, job.stage ?? null)
    if (job.status === "done" && job.result) return job.result
    if (job.status === "failed") throw new OdinApiError(job.error ?? "El análisis falló.")
    if (Date.now() > deadline) {
      throw new OdinApiError("El análisis está tardando demasiado. Intenta de nuevo.")
    }
    await pollDelay(JOB_POLL_INTERVAL_MS)
  }
}

export async function analyzeUrl(
  url: string,
  onStatus?: (status: JobStatus, stage: AnalyzeStage | null) => void
): Promise<AnalyzeResult> {
  const res = await postJson<AnalyzeResult | components["schemas"]["AnalyzeAccepted"]>(
    "/api/analyze",
    { url }
  )
  if ("job_id" in res) return pollJob(res.job_id, onStatus)
  return res
}

export function saveArticle(payload: SaveArticlePayload): Promise<ArticleAnalysis> {
  return postJson("/api/articles", payload)
}

export type DocumentalistCreated = components["schemas"]["DocumentalistCreated"]

/** Regenera el PIN de primer acceso. El PIN vuelve en claro una sola vez. */
export function resetDocumentalistPin(id: number): Promise<DocumentalistCreated> {
  return postJson(`/api/documentalists/${id}/pin`, {})
}

export type SourceOption = components["schemas"]["SourceOption"]

/** Los medios del registro de scrapers, para el formulario de captura. Ver
 *  `article_service.source_catalog`: no es lo mismo que `facets.sources`, que
 *  solo trae medios con reportes ya guardados. */
export function listSources(): Promise<SourceOption[]> {
  return request("/api/sources")
}

/** Da de alta un reporte. `alreadyExisted` distingue el 200 —esa URL ya estaba
 *  guardada y se devuelve la existente— del 201, para que el formulario avise
 *  en vez de dar por bueno un guardado que no ocurrió. */
export async function createArticle(
  payload: SaveArticlePayload
): Promise<{ article: ArticleAnalysis; alreadyExisted: boolean }> {
  const { data, status } = await requestWithStatus<ArticleAnalysis>("/api/articles", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  return { article: data, alreadyExisted: status === 200 }
}

// ── Reportes: listado y filtros ────────────────────────────────────────────

export function listArticles(params: ArticleListParams = {}): Promise<ArticleListResponse> {
  const qs = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue
    qs.set(key, String(value))
  }
  const s = qs.toString()
  return request<ArticleListResponse>(`/api/articles${s ? `?${s}` : ""}`)
}

export function getArticle(id: number): Promise<ArticleAnalysis> {
  return request<ArticleAnalysis>(`/api/articles/${id}`)
}

export function getArticleFilterOptions(): Promise<ArticleFilterOptions> {
  return request<ArticleFilterOptions>("/api/articles/filters")
}

export function updateArticle(
  id: number,
  payload: ArticleUpdatePayload
): Promise<ArticleAnalysis> {
  return putJson(`/api/articles/${id}`, payload)
}

export function deleteArticle(id: number): Promise<void> {
  return del(`/api/articles/${id}`)
}

export function updateEntity(id: number, payload: EntityUpdatePayload): Promise<EntityAnalysis> {
  return putJson(`/api/entities/${id}`, payload)
}

export function deleteEntity(id: number): Promise<void> {
  return del(`/api/entities/${id}`)
}

// ── Alias CRUD ──────────────────────────────────────────────────────────────

export function listAliases(q?: string): Promise<EntityAlias[]> {
  const qs = q ? `?q=${encodeURIComponent(q)}` : ""
  return request<EntityAlias[]>(`/api/aliases${qs}`)
}

export function createAlias(payload: AliasPayload): Promise<EntityAlias> {
  return postJson("/api/aliases", payload)
}

export function updateAlias(id: number, payload: AliasUpdatePayload): Promise<EntityAlias> {
  return putJson(`/api/aliases/${id}`, payload)
}

export function deleteAlias(id: number): Promise<void> {
  return del(`/api/aliases/${id}`)
}

export function toggleAlias(alias: EntityAlias): Promise<EntityAlias> {
  return updateAlias(alias.id, { is_active: !alias.is_active })
}

// ── Entidades canónicas ──────────────────────────────────────────────────────

export function listCanonicalEntities(
  params: CanonicalEntityListParams = {}
): Promise<CanonicalEntityListResponse> {
  const qs = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue
    qs.set(key, String(value))
  }
  const s = qs.toString()
  return request<CanonicalEntityListResponse>(`/api/canonical-entities${s ? `?${s}` : ""}`)
}

export function getCanonicalEntity(id: number): Promise<CanonicalEntityDetail> {
  return request<CanonicalEntityDetail>(`/api/canonical-entities/${id}`)
}

export function updateCanonicalEntity(
  id: number,
  payload: CanonicalEntityUpdatePayload
): Promise<CanonicalEntity> {
  return putJson(`/api/canonical-entities/${id}`, payload)
}

export function mergeCanonicalEntities(
  targetId: number,
  sourceId: number
): Promise<CanonicalEntity> {
  return postJson(`/api/canonical-entities/${targetId}/merge`, { source_id: sourceId })
}

// ── Lugar de la noticia ──────────────────────────────────────────────────────

export type LocalityNode = components["schemas"]["LocalityNode"]
export type Locality = components["schemas"]["LocalityResponse"]
export type ArticleLocality = components["schemas"]["ArticleLocalityResponse"]
export type ArticleLocalityPayload = components["schemas"]["ArticleLocalityPayload"]

/** Niveles del árbol, de mayor a menor. El orden gobierna el selector en
 *  cascada: cada desplegable se puebla con los hijos del nivel anterior. */
export const LOCALITY_LEVELS = [
  "PAIS",
  "MACRORREGION",
  "REGION",
  "PROVINCIA",
  "MUNICIPIO",
] as const
export type LocalityLevel = (typeof LOCALITY_LEVELS)[number]

/** Etiquetas del formulario que el cliente ya conoce (ver la captura de su
 *  sistema actual): País / Región / Provincia / Municipio. "Macrorregión" y
 *  "Región" son ambas regiones para él — la primera es la agrupación que usa
 *  hoy, la segunda el nivel oficial del Decreto 710-04. */
export const LOCALITY_LEVEL_LABELS: Record<LocalityLevel, string> = {
  PAIS: "País",
  MACRORREGION: "Región",
  REGION: "Subregión",
  PROVINCIA: "Provincia",
  MUNICIPIO: "Municipio",
}

export function getLocalityTree(): Promise<LocalityNode[]> {
  return request<LocalityNode[]>("/api/localities/tree")
}

export function listLocalities(params: {
  q?: string
  level?: string
  parent_id?: number
} = {}): Promise<Locality[]> {
  const qs = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue
    qs.set(key, String(value))
  }
  const s = qs.toString()
  return request<Locality[]>(`/api/localities${s ? `?${s}` : ""}`)
}

export function getArticleLocalities(articleId: number): Promise<ArticleLocality[]> {
  return request<ArticleLocality[]>(`/api/articles/${articleId}/localities`)
}

export function addArticleLocality(
  articleId: number,
  payload: ArticleLocalityPayload
): Promise<ArticleLocality> {
  return postJson(`/api/articles/${articleId}/localities`, payload)
}

/** Deja el artículo exactamente con los lugares enviados. Es lo que usa el
 *  formulario al guardar: el documentalista edita una lista y la manda
 *  completa, en vez de que el frontend calcule altas y bajas. */
export function replaceArticleLocalities(
  articleId: number,
  payload: ArticleLocalityPayload[]
): Promise<ArticleLocality[]> {
  return putJson(`/api/articles/${articleId}/localities`, payload)
}

export function deleteArticleLocality(articleId: number, linkId: number): Promise<void> {
  return del(`/api/articles/${articleId}/localities/${linkId}`)
}

// ── Documentalistas y exportación ──────────────────────────────────────────────────

export type Documentalist = components["schemas"]["DocumentalistResponse"]
export type DocumentalistKpiRow = components["schemas"]["DocumentalistKpiRow"]
export type DocumentalistPayload = components["schemas"]["DocumentalistPayload"]
export type DocumentalistUpdatePayload = components["schemas"]["DocumentalistUpdatePayload"]

export function listDocumentalists(): Promise<Documentalist[]> {
  return request<Documentalist[]>("/api/documentalists")
}

export function getDocumentalistKpi(
  params: { date_from?: string; date_to?: string } = {}
): Promise<DocumentalistKpiRow[]> {
  const qs = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue
    qs.set(key, String(value))
  }
  const s = qs.toString()
  return request<DocumentalistKpiRow[]>(`/api/documentalists/kpi${s ? `?${s}` : ""}`)
}

export function createDocumentalist(payload: DocumentalistPayload): Promise<Documentalist> {
  return postJson("/api/documentalists", payload)
}

export function updateDocumentalist(id: number, payload: DocumentalistUpdatePayload): Promise<Documentalist> {
  return putJson(`/api/documentalists/${id}`, payload)
}

/** Descarga el .docx de los reportes seleccionados.
 *
 *  No usa `request()` porque la respuesta es binaria, no JSON. La descarga se
 *  dispara con un enlace temporal sobre un blob: es lo único que funciona igual
 *  en todos los navegadores para un POST cuyo resultado es un archivo. */
export async function exportArticles(articleIds: number[]): Promise<void> {
  const headers = new Headers({ "Content-Type": "application/json" })
  const token = getToken()
  if (token) headers.set("Authorization", `Bearer ${token}`)

  const res = await fetch("/api/articles/export", {
    method: "POST",
    headers,
    body: JSON.stringify({ article_ids: articleIds }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new OdinApiError(body?.detail ?? "No se pudo exportar.")
  }

  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = "reportes-odin.docx"
  document.body.appendChild(link)
  link.click()
  link.remove()
  // Liberar el objeto: sin esto el blob queda retenido hasta recargar.
  URL.revokeObjectURL(url)
}
