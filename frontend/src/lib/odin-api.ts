import { clearSession, getToken, notifyAuthExpired, setSession } from "@/lib/auth"
import type { components } from "@/lib/api-types"

// Los tipos de forma (Article*, Entity*, CanonicalEntity*, Alias*) salen del
// OpenAPI real de la API (`response_model=` en api.py/auth.py) en vez de
// mantenerse a mano: era la tercera copia del mismo listado de campos, junto
// a los modelos SQLAlchemy y los serializadores de api.py (§9.2 de task.md,
// tarea 25). Para regenerar tras un cambio de schema: `npm run generate:types`.

export type EntityAnalysis = components["schemas"]["EntityMention"]

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
  ArticleAnalysis,
  | "id"
  | "already_saved"
  | "analyzer_name"
  | "analyzer_model"
  | "analyzer_version"
  | "analysis_schema_version"
  | "analyzed_at"
>

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
  date_from?: string
  date_to?: string
  sort?: "recent" | "oldest"
  limit?: number
  offset?: number
}

export type EntityAlias = components["schemas"]["EntityAliasResponse"]

export type AliasPayload = components["schemas"]["AliasPayload"]

export type AliasUpdatePayload = components["schemas"]["AliasUpdatePayload"]

// ── Entidades canónicas ──────────────────────────────────────────────────────

export type CanonicalEntity = components["schemas"]["CanonicalEntityResponse"]

export type CanonicalEntityDetail = components["schemas"]["CanonicalEntityDetailResponse"]

export type CanonicalEntityListResponse = components["schemas"]["CanonicalEntityListResponse"]

export interface CanonicalEntityListParams {
  q?: string
  type?: "ORG" | "PERSON"
  limit?: number
  offset?: number
}

export type CanonicalEntityUpdatePayload = components["schemas"]["CanonicalEntityUpdatePayload"]

export class OdinApiError extends Error {}

const BASE = ""

async function request<T>(path: string, init?: RequestInit): Promise<T> {
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
  if (res.status === 204) return undefined as unknown as T
  return res.json()
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
// opcional, para que la UI muestre progreso real en vez de un spinner ciego.

export type JobStatus = components["schemas"]["JobResponse"]["status"]

const JOB_POLL_INTERVAL_MS = 1500
const JOB_POLL_TIMEOUT_MS = 120_000

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function pollJob(
  jobId: string,
  onStatus?: (status: JobStatus) => void
): Promise<ArticleAnalysis> {
  const deadline = Date.now() + JOB_POLL_TIMEOUT_MS
  for (;;) {
    const job = await request<components["schemas"]["JobResponse"]>(`/api/jobs/${jobId}`)
    onStatus?.(job.status)
    if (job.status === "done" && job.result) return job.result
    if (job.status === "failed") throw new OdinApiError(job.error ?? "El análisis falló.")
    if (Date.now() > deadline) {
      throw new OdinApiError("El análisis está tardando demasiado. Intenta de nuevo.")
    }
    await sleep(JOB_POLL_INTERVAL_MS)
  }
}

export async function analyzeUrl(
  url: string,
  onStatus?: (status: JobStatus) => void
): Promise<ArticleAnalysis> {
  const res = await postJson<ArticleAnalysis | components["schemas"]["AnalyzeAccepted"]>(
    "/api/analyze",
    { url }
  )
  if ("job_id" in res) return pollJob(res.job_id, onStatus)
  return res
}

export function saveArticle(payload: SaveArticlePayload): Promise<ArticleAnalysis> {
  return postJson("/api/articles", payload)
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

// ── Scraper de política ─────────────────────────────────────────────────────
//
// POST /api/scrape-jobs encola una corrida del scraper de política dominicana
// sobre las 9 fuentes permitidas (target/tope por fuente/analizador) y
// responde 202 + job_id de inmediato — la corrida real tarda varios minutos.
// `pollScrapeJob` hace polling de GET /api/scrape-jobs/{id}, igual patrón que
// `pollJob` para /api/analyze, pero sin timeout fijo (acá "tardar mucho" es
// normal, no un error) y con `onUpdate` recibiendo el job completo en cada
// tick para que la UI dibuje el progreso por fuente.

export type ScrapeJobStartPayload = components["schemas"]["ScrapeJobStartRequest"]
export type ScrapeJob = components["schemas"]["ScrapeJobResponse"]
export type ScrapeJobStatus = ScrapeJob["status"]
export type ScrapeSourceProgress = components["schemas"]["ScrapeSourceProgress"]

const SCRAPE_JOB_POLL_INTERVAL_MS = 2000

const SCRAPE_JOB_TERMINAL_STATUSES: ScrapeJobStatus[] = ["done", "failed", "cancelled"]

export function startScrapeJob(payload: ScrapeJobStartPayload): Promise<components["schemas"]["ScrapeJobAccepted"]> {
  return postJson("/api/scrape-jobs", payload)
}

export function getScrapeJob(jobId: string): Promise<ScrapeJob> {
  return request<ScrapeJob>(`/api/scrape-jobs/${jobId}`)
}

export function listScrapeJobs(limit = 1): Promise<ScrapeJob[]> {
  return request<ScrapeJob[]>(`/api/scrape-jobs?limit=${limit}`)
}

export function cancelScrapeJob(jobId: string): Promise<ScrapeJob> {
  return postJson(`/api/scrape-jobs/${jobId}/cancel`, {})
}

/** Hace polling de un job hasta que llega a un estado terminal, invocando
 *  `onUpdate` en cada tick. Devuelve una función `stop()` para cortar el
 *  polling desde afuera (p. ej. si el componente se desmonta). */
export function pollScrapeJob(
  jobId: string,
  onUpdate: (job: ScrapeJob) => void
): () => void {
  let stopped = false
  ;(async () => {
    while (!stopped) {
      let job: ScrapeJob
      try {
        job = await getScrapeJob(jobId)
      } catch {
        // Error de red transitorio durante el polling: reintenta en el
        // próximo tick en vez de tumbar el polling entero.
        await sleep(SCRAPE_JOB_POLL_INTERVAL_MS)
        continue
      }
      if (stopped) return
      onUpdate(job)
      if (SCRAPE_JOB_TERMINAL_STATUSES.includes(job.status)) return
      await sleep(SCRAPE_JOB_POLL_INTERVAL_MS)
    }
  })()
  return () => {
    stopped = true
  }
}
