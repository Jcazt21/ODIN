import { useCallback, useEffect, useRef, useState } from "react"
import { ChevronLeft, ChevronRight, Pencil, RotateCcw, Search, Trash2, X } from "lucide-react"
import { Select } from "@/components/ui/select"
import { SentimentBadge } from "@/components/SentimentBadge"
import { AnalysisCard, type AnalysisCardFields } from "@/components/AnalysisCard"
import { EntitiesCard } from "@/components/EntitiesCard"
import { useConfirm } from "@/lib/dialog"
import { FRAMING_LABELS, HEADLINE_LABELS, LEAD_LABELS, SENTIMENT_LABELS, SOURCE_LABELS } from "@/lib/labels"
import { formatDateShort } from "@/lib/format"
import {
  listArticles,
  getArticle,
  getArticleFilterOptions,
  updateArticle,
  deleteArticle,
  OdinApiError,
  type ArticleAnalysis,
  type ArticleFilterOptions,
  type ArticleListParams,
  type ArticleSummary,
  type ArticleUpdatePayload,
} from "@/lib/odin-api"

const PAGE_SIZE = 12

type HardDataFilter = "" | "true" | "false"
type EditableFields = Pick<
  AnalysisCardFields,
  | "main_topic"
  | "topic_keywords"
  | "overall_sentiment"
  | "sentiment_score"
  | "framing"
  | "headline_intent"
  | "lead_orientation"
  | "source_quality"
  | "has_hard_data"
  | "dominant_actor"
  | "blamed_actor"
  | "credited_actor"
>

function toEditForm(article: ArticleAnalysis): EditableFields {
  return {
    main_topic: article.main_topic,
    topic_keywords: article.topic_keywords,
    overall_sentiment: article.overall_sentiment,
    sentiment_score: article.sentiment_score,
    framing: article.framing,
    headline_intent: article.headline_intent,
    lead_orientation: article.lead_orientation,
    dominant_actor: article.dominant_actor,
    source_quality: article.source_quality,
    has_hard_data: article.has_hard_data,
    blamed_actor: article.blamed_actor,
    credited_actor: article.credited_actor,
  }
}

const EMPTY_FILTERS: ArticleListParams = { sort: "recent" }

// ─────────────────────────────────────────────────────────────────────────────
// Filtros
// ─────────────────────────────────────────────────────────────────────────────

function DateField({
  label,
  value,
  onChange,
}: {
  label: string
  value: string
  onChange: (v: string) => void
}) {
  return (
    <label
      className="flex h-8 items-center gap-1.5 rounded-[7px] border px-[11px]"
      style={{ background: "var(--surface-2)", borderColor: "var(--border)" }}
    >
      <span className="text-[11.5px]" style={{ color: "var(--faint)" }}>
        {label}
      </span>
      <input
        type="date"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="flex-1 bg-transparent text-[12.5px] outline-none"
      />
    </label>
  )
}

function FilterBar({
  filters,
  onChange,
  hardData,
  onHardDataChange,
  facets,
  onReset,
  hasActiveFilters,
  total,
  loaded,
}: {
  filters: ArticleListParams
  onChange: (patch: Partial<ArticleListParams>) => void
  hardData: HardDataFilter
  onHardDataChange: (v: HardDataFilter) => void
  facets: ArticleFilterOptions | null
  onReset: () => void
  hasActiveFilters: boolean
  total: number
  loaded: number
}) {
  return (
    <div
      className="rounded-xl border p-[18px]"
      style={{ background: "var(--panel)", borderColor: "var(--border)", boxShadow: "var(--shadow-sm)" }}
    >
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <div className="flex items-baseline gap-2.5">
          <h1 className="text-[19px] font-semibold">Reportes</h1>
          <span className="text-[12.5px]" style={{ color: "var(--faint)" }}>
            {loaded} de {total} reportes
          </span>
        </div>
        {hasActiveFilters && (
          <button
            type="button"
            onClick={onReset}
            className="inline-flex items-center gap-1.5 text-[12.5px]"
            style={{ color: "var(--muted-foreground)" }}
          >
            <RotateCcw className="size-3.5" />
            Limpiar filtros
          </button>
        )}
      </div>

      <div className="grid gap-[10px]" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(168px, 1fr))" }}>
        <div className="relative">
          <Search className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2" style={{ color: "var(--faint)" }} />
          <input
            value={filters.q ?? ""}
            onChange={(e) => onChange({ q: e.target.value || undefined })}
            placeholder="Título o tema…"
            className="h-8 w-full rounded-[7px] border pr-2 pl-8 text-[13px] outline-none"
            style={{ background: "var(--surface-2)", borderColor: "var(--border)" }}
          />
        </div>
        <div className="relative">
          <Search className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2" style={{ color: "var(--faint)" }} />
          <input
            value={filters.entity ?? ""}
            onChange={(e) => onChange({ entity: e.target.value || undefined })}
            placeholder="Entidad mencionada…"
            className="h-8 w-full rounded-[7px] border pr-2 pl-8 text-[13px] outline-none"
            style={{ background: "var(--surface-2)", borderColor: "var(--border)" }}
          />
        </div>

        <Select value={filters.source ?? ""} onChange={(e) => onChange({ source: e.target.value || undefined })}>
          <option value="">Todas las fuentes</option>
          {facets?.sources.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </Select>
        <Select value={filters.sentiment ?? ""} onChange={(e) => onChange({ sentiment: e.target.value || undefined })}>
          <option value="">Todo sentimiento</option>
          {(facets?.sentiments ?? []).map((s) => (
            <option key={s} value={s}>
              {SENTIMENT_LABELS[s] ?? s}
            </option>
          ))}
        </Select>
        <Select value={filters.framing ?? ""} onChange={(e) => onChange({ framing: e.target.value || undefined })}>
          <option value="">Todo encuadre</option>
          {(facets?.framing ?? []).map((v) => (
            <option key={v} value={v}>
              {FRAMING_LABELS[v] ?? v}
            </option>
          ))}
        </Select>
        <Select
          value={filters.headline_intent ?? ""}
          onChange={(e) => onChange({ headline_intent: e.target.value || undefined })}
        >
          <option value="">Todo titular</option>
          {(facets?.headline_intent ?? []).map((v) => (
            <option key={v} value={v}>
              {HEADLINE_LABELS[v] ?? v}
            </option>
          ))}
        </Select>
        <Select
          value={filters.lead_orientation ?? ""}
          onChange={(e) => onChange({ lead_orientation: e.target.value || undefined })}
        >
          <option value="">Todo lead</option>
          {(facets?.lead_orientation ?? []).map((v) => (
            <option key={v} value={v}>
              {LEAD_LABELS[v] ?? v}
            </option>
          ))}
        </Select>
        <Select
          value={filters.source_quality ?? ""}
          onChange={(e) => onChange({ source_quality: e.target.value || undefined })}
        >
          <option value="">Toda calidad de fuente</option>
          {(facets?.source_quality ?? []).map((v) => (
            <option key={v} value={v}>
              {SOURCE_LABELS[v] ?? v}
            </option>
          ))}
        </Select>
        <Select value={hardData} onChange={(e) => onHardDataChange(e.target.value as HardDataFilter)}>
          <option value="">Datos duros: todos</option>
          <option value="true">Con datos duros</option>
          <option value="false">Sin datos duros</option>
        </Select>
        <DateField label="Desde" value={filters.date_from ?? ""} onChange={(v) => onChange({ date_from: v || undefined })} />
        <DateField label="Hasta" value={filters.date_to ?? ""} onChange={(v) => onChange({ date_to: v || undefined })} />
        <Select value={filters.sort ?? "recent"} onChange={(e) => onChange({ sort: e.target.value as "recent" | "oldest" })}>
          <option value="recent">Más recientes</option>
          <option value="oldest">Más antiguos</option>
        </Select>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Tabla
// ─────────────────────────────────────────────────────────────────────────────

function ReportsTable({
  items,
  loading,
  onOpen,
  sortDir,
  onToggleSort,
}: {
  items: ArticleSummary[]
  loading: boolean
  onOpen: (id: number) => void
  sortDir: "recent" | "oldest"
  onToggleSort: () => void
}) {
  return (
    <div
      className="overflow-hidden rounded-xl border"
      style={{ background: "var(--panel)", borderColor: "var(--border)" }}
    >
      <table className="w-full border-collapse text-[13px]">
        <thead>
          <tr style={{ background: "var(--surface-2)" }}>
            <th
              onClick={onToggleSort}
              className="cursor-pointer border-b px-[14px] py-[10px] text-left font-mono text-[10.5px] font-medium tracking-[0.1em] uppercase whitespace-nowrap select-none"
              style={{ borderColor: "var(--border)", color: "var(--primary)" }}
            >
              Fecha {sortDir === "recent" ? "↓" : "↑"}
            </th>
            {["Artículo", "Fuente", "Sentimiento", "Encuadre"].map((h) => (
              <th
                key={h}
                className="border-b px-[14px] py-[10px] text-left font-mono text-[10.5px] font-medium tracking-[0.1em] uppercase whitespace-nowrap"
                style={{ borderColor: "var(--border)", color: "var(--faint)" }}
              >
                {h}
              </th>
            ))}
            <th
              className="border-b px-[14px] py-[10px] text-right font-mono text-[10.5px] font-medium tracking-[0.1em] uppercase whitespace-nowrap"
              style={{ borderColor: "var(--border)", color: "var(--faint)" }}
            >
              Ent.
            </th>
            <th
              className="border-b px-[14px] py-[10px] text-center font-mono text-[10.5px] font-medium tracking-[0.1em] uppercase whitespace-nowrap"
              style={{ borderColor: "var(--border)", color: "var(--faint)" }}
            >
              Datos
            </th>
          </tr>
        </thead>
        <tbody>
          {loading
            ? Array.from({ length: 6 }).map((_, i) => (
                <tr key={i} className="border-b" style={{ borderColor: "var(--border)" }}>
                  <td className="px-[14px] py-3" colSpan={7}>
                    <div
                      className="h-4 rounded"
                      style={{ background: "var(--surface-3)", animation: "odinPulse 1.6s ease-in-out infinite" }}
                    />
                  </td>
                </tr>
              ))
            : items.map((a) => (
                <tr
                  key={a.id}
                  onClick={() => onOpen(a.id)}
                  className="cursor-pointer border-b transition-colors"
                  style={{ borderColor: "var(--border)" }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surface-2)")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                >
                  <td className="px-[14px] py-3 align-top font-mono text-[11.5px] whitespace-nowrap" style={{ color: "var(--faint)" }}>
                    {formatDateShort(a.published_at)}
                  </td>
                  <td className="max-w-[380px] px-[14px] py-3 align-top">
                    <p className="font-medium leading-[1.4]">{a.title}</p>
                    {a.main_topic && (
                      <p className="mt-0.5 text-[12px]" style={{ color: "var(--muted-foreground)" }}>
                        {a.main_topic}
                      </p>
                    )}
                  </td>
                  <td className="px-[14px] py-3 align-top" style={{ color: "var(--muted-foreground)" }}>
                    {a.source}
                  </td>
                  <td className="px-[14px] py-3 align-top">
                    <SentimentBadge sentiment={a.overall_sentiment} score={a.sentiment_score} />
                  </td>
                  <td className="px-[14px] py-3 align-top">
                    {a.framing ? (
                      <span
                        className="rounded-[5px] border px-2 py-0.5 text-[11.5px]"
                        style={{ background: "var(--surface-2)", borderColor: "var(--border)", color: "var(--muted-foreground)" }}
                      >
                        {FRAMING_LABELS[a.framing] ?? a.framing}
                      </span>
                    ) : (
                      <span style={{ color: "var(--faint)" }}>—</span>
                    )}
                  </td>
                  <td className="px-[14px] py-3 text-right align-top font-mono" style={{ color: "var(--muted-foreground)" }}>
                    {a.entity_count}
                  </td>
                  <td className="px-[14px] py-3 text-center align-top">
                    {a.has_hard_data ? (
                      <span style={{ color: "var(--primary)" }}>●</span>
                    ) : (
                      <span style={{ color: "var(--faint)" }}>—</span>
                    )}
                  </td>
                </tr>
              ))}
        </tbody>
      </table>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Detalle de un reporte
// ─────────────────────────────────────────────────────────────────────────────

function ReportDetail({ id, onBack }: { id: number; onBack: () => void }) {
  const [article, setArticle] = useState<ArticleAnalysis | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)
  const [editForm, setEditForm] = useState<EditableFields | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const confirm = useConfirm()

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    getArticle(id)
      .then((a) => {
        if (!cancelled) setArticle(a)
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof OdinApiError ? e.message : "No se pudo cargar el reporte.")
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [id])

  function startEditing() {
    if (!article) return
    setEditForm(toEditForm(article))
    setSaveError(null)
    setEditing(true)
  }

  async function handleSaveEdit() {
    if (!article || !editForm) return
    setSaving(true)
    setSaveError(null)
    try {
      const updated = await updateArticle(article.id as number, editForm as ArticleUpdatePayload)
      setArticle(updated)
      setEditing(false)
    } catch (e) {
      setSaveError(e instanceof OdinApiError ? e.message : "Error guardando la rectificación.")
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    if (!article) return
    const ok = await confirm({
      title: "¿Eliminar este reporte?",
      body: `Se eliminará permanentemente "${article.title}". Esta acción no se puede deshacer.`,
      confirmLabel: "Eliminar",
      danger: true,
    })
    if (!ok) return
    setDeleting(true)
    setDeleteError(null)
    try {
      await deleteArticle(article.id as number)
      onBack()
    } catch (e) {
      setDeleteError(e instanceof OdinApiError ? e.message : "Error eliminando el reporte.")
      setDeleting(false)
    }
  }

  const cardValue: AnalysisCardFields | null = article
    ? editing && editForm
      ? { ...article, ...editForm }
      : article
    : null

  return (
    <div className="flex w-full flex-col gap-4">
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex items-center gap-1.5 text-[13px]"
          style={{ color: "var(--muted-foreground)" }}
        >
          <ChevronLeft className="size-3.5" />
          Volver a la lista
        </button>
        {article && !editing && (
          <div className="flex gap-2">
            <button
              type="button"
              onClick={startEditing}
              className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-[13px]"
              style={{ borderColor: "var(--border)" }}
            >
              <Pencil className="size-3.5" />
              Editar
            </button>
            <button
              type="button"
              disabled={deleting}
              onClick={handleDelete}
              className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-[13px] disabled:opacity-60"
              style={{ borderColor: "var(--border)", color: "var(--neg)" }}
            >
              <Trash2 className="size-3.5" />
              {deleting ? "Eliminando…" : "Eliminar"}
            </button>
          </div>
        )}
        {article && editing && (
          <div className="flex gap-2">
            <button
              type="button"
              disabled={saving}
              onClick={() => setEditing(false)}
              className="rounded-lg border px-3 py-1.5 text-[13px]"
              style={{ borderColor: "var(--border)" }}
            >
              Cancelar
            </button>
            <button
              type="button"
              disabled={saving}
              onClick={handleSaveEdit}
              className="rounded-lg px-3.5 py-1.5 text-[13px] font-semibold disabled:opacity-60"
              style={{ background: "var(--primary)", color: "var(--accent-fg)" }}
            >
              {saving ? "Guardando…" : "Guardar cambios"}
            </button>
          </div>
        )}
      </div>

      {editing && (
        <p className="text-[12.5px]" style={{ color: "var(--muted-foreground)" }}>
          Solo se corrige el análisis (tema, sentimiento, encuadre); título, cuerpo y URL no se
          pueden editar aquí.
        </p>
      )}

      {saveError && (
        <div role="alert" className="rounded-[7px] border px-3 py-2.5 text-[12.5px]" style={{ background: "var(--neg-soft)", borderColor: "var(--neg)", color: "var(--neg)" }}>
          <strong>No se pudo guardar</strong> {saveError}
        </div>
      )}
      {deleteError && (
        <div role="alert" className="rounded-[7px] border px-3 py-2.5 text-[12.5px]" style={{ background: "var(--neg-soft)", borderColor: "var(--neg)", color: "var(--neg)" }}>
          <strong>No se pudo eliminar</strong> {deleteError}
        </div>
      )}
      {error && (
        <div role="alert" className="rounded-[7px] border px-3 py-2.5 text-[12.5px]" style={{ background: "var(--neg-soft)", borderColor: "var(--neg)", color: "var(--neg)" }}>
          <strong>No se pudo cargar</strong> {error}
        </div>
      )}

      {loading && (
        <div className="space-y-2 rounded-xl border p-[22px]" style={{ borderColor: "var(--border)" }}>
          <div className="h-6 w-3/4 rounded" style={{ background: "var(--surface-3)", animation: "odinPulse 1.6s ease-in-out infinite" }} />
          <div className="h-4 w-1/2 rounded" style={{ background: "var(--surface-3)", animation: "odinPulse 1.6s ease-in-out 0.15s infinite" }} />
        </div>
      )}

      {article && cardValue && (
        <>
          <AnalysisCard
            value={cardValue}
            editable={editing}
            onChange={(patch) => setEditForm((f) => (f ? { ...f, ...patch } : f))}
          />
          <EntitiesCard entities={article.entities} editable={false} />
        </>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Componente principal
// ─────────────────────────────────────────────────────────────────────────────

export function ReportsList() {
  const [filters, setFilters] = useState<ArticleListParams>(EMPTY_FILTERS)
  const [hardData, setHardData] = useState<HardDataFilter>("")
  const [page, setPage] = useState(0)

  const [data, setData] = useState<{ total: number; items: ArticleSummary[] } | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [facets, setFacets] = useState<ArticleFilterOptions | null>(null)

  const [selectedId, setSelectedId] = useState<number | null>(null)

  useEffect(() => {
    getArticleFilterOptions()
      .then(setFacets)
      .catch(() => {})
  }, [])

  // Evita que una respuesta vieja (p. ej. de un filtro anterior, más lenta en
  // resolver que la siguiente) sobrescriba datos más nuevos ya renderizados.
  const requestIdRef = useRef(0)

  const load = useCallback(async () => {
    const requestId = ++requestIdRef.current
    setLoading(true)
    setError(null)
    try {
      const res = await listArticles({
        ...filters,
        has_hard_data: hardData === "" ? undefined : hardData === "true",
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      })
      if (requestIdRef.current !== requestId) return
      setData(res)
    } catch (e) {
      if (requestIdRef.current !== requestId) return
      setError(e instanceof OdinApiError ? e.message : "No se pudo conectar con la API de Odin.")
    } finally {
      if (requestIdRef.current === requestId) setLoading(false)
    }
  }, [filters, hardData, page])

  // Solo los campos de texto libre (q, entity) necesitan debounce; clicks en
  // selects, fechas, orden o paginación deben reflejarse de inmediato — antes
  // heredaban los mismos 300ms de espera del texto y se sentían lentos.
  const isFirstLoad = useRef(true)
  const prevTextRef = useRef({ q: filters.q, entity: filters.entity })
  useEffect(() => {
    if (isFirstLoad.current) {
      isFirstLoad.current = false
      prevTextRef.current = { q: filters.q, entity: filters.entity }
      load()
      return
    }
    const textChanged = filters.q !== prevTextRef.current.q || filters.entity !== prevTextRef.current.entity
    prevTextRef.current = { q: filters.q, entity: filters.entity }
    if (!textChanged) {
      load()
      return
    }
    const t = setTimeout(load, 300)
    return () => clearTimeout(t)
  }, [load, filters.q, filters.entity])

  function updateFilters(patch: Partial<ArticleListParams>) {
    setPage(0)
    setFilters((f) => ({ ...f, ...patch }))
  }

  function updateHardData(v: HardDataFilter) {
    setPage(0)
    setHardData(v)
  }

  function resetFilters() {
    setPage(0)
    setFilters(EMPTY_FILTERS)
    setHardData("")
  }

  const hasActiveFilters =
    hardData !== "" || Object.entries(filters).some(([k, v]) => k !== "sort" && v !== undefined && v !== "")

  const total = data?.total ?? 0
  const items = data?.items ?? []
  const to = Math.min(total, (page + 1) * PAGE_SIZE)

  if (selectedId != null) {
    return <ReportDetail id={selectedId} onBack={() => setSelectedId(null)} />
  }

  return (
    <div className="flex w-full flex-col gap-4">
      <FilterBar
        filters={filters}
        onChange={updateFilters}
        hardData={hardData}
        onHardDataChange={updateHardData}
        facets={facets}
        onReset={resetFilters}
        hasActiveFilters={hasActiveFilters}
        total={total}
        loaded={items.length}
      />

      {error && (
        <div role="alert" className="rounded-[7px] border px-3 py-2.5 text-[12.5px]" style={{ background: "var(--neg-soft)", borderColor: "var(--neg)", color: "var(--neg)" }}>
          {error}
        </div>
      )}

      {!loading && items.length === 0 ? (
        <div
          className="flex flex-col items-center gap-3 rounded-xl border py-14 text-center"
          style={{ borderColor: "var(--border)", background: "var(--panel)" }}
        >
          <p className="text-[14.5px] font-semibold">Sin resultados</p>
          <p className="max-w-[38ch] text-[13px]" style={{ color: "var(--muted-foreground)" }}>
            Ningún reporte coincide con los filtros aplicados.
          </p>
          {hasActiveFilters && (
            <button
              type="button"
              onClick={resetFilters}
              className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-[13px]"
              style={{ borderColor: "var(--border)" }}
            >
              <X className="size-3.5" />
              Quitar filtros
            </button>
          )}
        </div>
      ) : (
        <ReportsTable
          items={items}
          loading={loading}
          onOpen={setSelectedId}
          sortDir={filters.sort ?? "recent"}
          onToggleSort={() => updateFilters({ sort: filters.sort === "oldest" ? "recent" : "oldest" })}
        />
      )}

      {total > PAGE_SIZE && (
        <div
          className="flex items-center justify-between rounded-xl border px-[14px] py-[11px]"
          style={{ background: "var(--surface-2)", borderColor: "var(--border)" }}
        >
          <span className="text-[12px]" style={{ color: "var(--faint)" }}>
            Página {page + 1} de {Math.max(1, Math.ceil(total / PAGE_SIZE))} · {items.length} visibles
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={page === 0 || loading}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              className="inline-flex items-center gap-1 rounded-[6px] border px-2.5 py-1 text-[12.5px] disabled:opacity-50"
              style={{ background: "var(--surface)", borderColor: "var(--border)" }}
            >
              <ChevronLeft className="size-3.5" />
              Anterior
            </button>
            <button
              type="button"
              disabled={to >= total || loading}
              onClick={() => setPage((p) => p + 1)}
              className="inline-flex items-center gap-1 rounded-[6px] border px-2.5 py-1 text-[12.5px] disabled:opacity-50"
              style={{ background: "var(--surface)", borderColor: "var(--border)" }}
            >
              Siguiente
              <ChevronRight className="size-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
