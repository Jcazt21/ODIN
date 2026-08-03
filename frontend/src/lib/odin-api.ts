export interface EntityAnalysis {
  name: string
  type: "PERSON" | "ORG" | string
  mentions_count: number
  sentiment_toward: "POS" | "NEG" | "NEU" | null
  sentiment_score: number | null
  context: string | null
}

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

export interface ArticleAnalysis {
  already_saved: boolean
  id: number | null
  source: string
  url: string
  title: string
  authors: string | null
  section: string | null
  published_at: string | null
  body: string
  main_topic: string | null
  topic_keywords: string | null
  overall_sentiment: "POS" | "NEG" | "NEU" | null
  sentiment_score: number | null
  // Análisis de encuadre — null cuando analizó el modelo local
  framing: Framing | null
  headline_intent: HeadlineIntent | null
  lead_orientation: LeadOrientation | null
  dominant_actor: string | null
  source_quality: SourceQuality | null
  has_hard_data: boolean | null
  blamed_actor: string | null
  credited_actor: string | null
  entities: EntityAnalysis[]
}

export type SaveArticlePayload = Omit<ArticleAnalysis, "id" | "already_saved">

export interface ArticleSummary {
  id: number
  source: string
  url: string
  title: string
  section: string | null
  published_at: string | null
  scraped_at: string
  main_topic: string | null
  overall_sentiment: "POS" | "NEG" | "NEU" | null
  sentiment_score: number | null
  framing: Framing | null
  headline_intent: HeadlineIntent | null
  lead_orientation: LeadOrientation | null
  source_quality: SourceQuality | null
  has_hard_data: boolean | null
  dominant_actor: string | null
  blamed_actor: string | null
  credited_actor: string | null
  entity_count: number
}

export interface ArticleListResponse {
  total: number
  limit: number
  offset: number
  items: ArticleSummary[]
}

export interface ArticleFilterOptions {
  sources: string[]
  sections: string[]
  sentiments: string[]
  framing: string[]
  headline_intent: string[]
  lead_orientation: string[]
  source_quality: string[]
}

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

export interface EntityAlias {
  id: number
  alias: string
  canonical_name: string
  type: "ORG" | "PERSON"
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface AliasPayload {
  alias: string
  canonical_name: string
  type: "ORG" | "PERSON"
  is_active?: boolean
}

export interface AliasUpdatePayload {
  alias?: string
  canonical_name?: string
  type?: "ORG" | "PERSON"
  is_active?: boolean
}

export class OdinApiError extends Error {}

const BASE = ""

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, init)
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

export function analyzeUrl(url: string): Promise<ArticleAnalysis> {
  return postJson("/api/analyze", { url })
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
