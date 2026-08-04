import { useCallback, useEffect, useState } from "react"
import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Pencil,
  RotateCcw,
  Search,
  Trash2,
  X,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { SentimentBadge } from "@/components/SentimentBadge"
import { cn } from "@/lib/utils"
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

const FRAMING_LABELS: Record<string, string> = {
  crisis_conflicto: "Crisis / conflicto",
  logro_institucional: "Logro institucional",
  negligencia: "Negligencia",
  crecimiento: "Crecimiento",
  denuncia: "Denuncia",
  neutro_informativo: "Neutro informativo",
}
const HEADLINE_LABELS: Record<string, string> = {
  informativo: "Informativo",
  alarmista: "Alarmista",
  sensacionalista: "Sensacionalista",
}
const LEAD_LABELS: Record<string, string> = {
  social: "Social (ciudadanía)",
  oficialista: "Oficialista",
  tecnico: "Técnico (datos)",
}
const SOURCE_LABELS: Record<string, string> = {
  citas_directas: "Citas directas",
  testimonios_anonimos: "Testimonios anónimos",
  datos_duros: "Datos duros",
  mixtas: "Mixtas",
  sin_fuentes: "Sin fuentes",
}
const SENTIMENT_LABELS: Record<string, string> = {
  POS: "Positivo",
  NEG: "Negativo",
  NEU: "Neutro",
}

const selectClass =
  "h-8 rounded-lg border border-input bg-transparent px-2 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30"

function formatDate(value: string | null) {
  if (!value) return "Fecha desconocida"
  try {
    return new Intl.DateTimeFormat("es-DO", {
      dateStyle: "long",
      timeStyle: "short",
    }).format(new Date(value))
  } catch {
    return value
  }
}

function isLowConfidence(ent: { extraction_confidence?: number }) {
  return typeof ent.extraction_confidence === "number" && ent.extraction_confidence < 0.9
}

const SENTIMENT_BAR_COLOR: Record<string, string> = {
  POS: "bg-success",
  NEG: "bg-destructive",
  NEU: "bg-muted-foreground/50",
}

function toEditForm(article: ArticleAnalysis): ArticleUpdatePayload {
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

type HardDataFilter = "" | "true" | "false"

const EMPTY_FILTERS: ArticleListParams = { sort: "recent" }

// ─────────────────────────────────────────────────────────────────────────────
// Filtros
// ─────────────────────────────────────────────────────────────────────────────

function FilterBar({
  filters,
  onChange,
  hardData,
  onHardDataChange,
  facets,
  onReset,
  hasActiveFilters,
}: {
  filters: ArticleListParams
  onChange: (patch: Partial<ArticleListParams>) => void
  hardData: HardDataFilter
  onHardDataChange: (v: HardDataFilter) => void
  facets: ArticleFilterOptions | null
  onReset: () => void
  hasActiveFilters: boolean
}) {
  return (
    <Card>
      <CardContent className="space-y-3 pt-5">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={filters.q ?? ""}
              onChange={(e) => onChange({ q: e.target.value || undefined })}
              placeholder="Buscar por título o tema…"
              className="pl-8"
            />
          </div>
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={filters.entity ?? ""}
              onChange={(e) => onChange({ entity: e.target.value || undefined })}
              placeholder="Figura pública o empresa…"
              className="pl-8"
            />
          </div>
          <select
            className={selectClass}
            value={filters.source ?? ""}
            onChange={(e) => onChange({ source: e.target.value || undefined })}
          >
            <option value="">Todas las fuentes</option>
            {facets?.sources.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>

        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <select
            className={selectClass}
            value={filters.sentiment ?? ""}
            onChange={(e) => onChange({ sentiment: e.target.value || undefined })}
          >
            <option value="">Cualquier sentimiento</option>
            {(facets?.sentiments ?? []).map((s) => (
              <option key={s} value={s}>
                {SENTIMENT_LABELS[s] ?? s}
              </option>
            ))}
          </select>
          <select
            className={selectClass}
            value={filters.framing ?? ""}
            onChange={(e) => onChange({ framing: e.target.value || undefined })}
          >
            <option value="">Cualquier encuadre</option>
            {(facets?.framing ?? []).map((v) => (
              <option key={v} value={v}>
                {FRAMING_LABELS[v] ?? v}
              </option>
            ))}
          </select>
          <select
            className={selectClass}
            value={filters.headline_intent ?? ""}
            onChange={(e) => onChange({ headline_intent: e.target.value || undefined })}
          >
            <option value="">Cualquier titular</option>
            {(facets?.headline_intent ?? []).map((v) => (
              <option key={v} value={v}>
                {HEADLINE_LABELS[v] ?? v}
              </option>
            ))}
          </select>
          <select
            className={selectClass}
            value={filters.lead_orientation ?? ""}
            onChange={(e) => onChange({ lead_orientation: e.target.value || undefined })}
          >
            <option value="">Cualquier lead</option>
            {(facets?.lead_orientation ?? []).map((v) => (
              <option key={v} value={v}>
                {LEAD_LABELS[v] ?? v}
              </option>
            ))}
          </select>
        </div>

        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
          <select
            className={selectClass}
            value={filters.source_quality ?? ""}
            onChange={(e) => onChange({ source_quality: e.target.value || undefined })}
          >
            <option value="">Cualquier tipo de fuente</option>
            {(facets?.source_quality ?? []).map((v) => (
              <option key={v} value={v}>
                {SOURCE_LABELS[v] ?? v}
              </option>
            ))}
          </select>
          <select
            className={selectClass}
            value={hardData}
            onChange={(e) => onHardDataChange(e.target.value as HardDataFilter)}
          >
            <option value="">Datos duros: todos</option>
            <option value="true">Con datos duros</option>
            <option value="false">Sin datos duros</option>
          </select>
          <Input
            type="date"
            value={filters.date_from ?? ""}
            onChange={(e) => onChange({ date_from: e.target.value || undefined })}
            aria-label="Desde"
          />
          <Input
            type="date"
            value={filters.date_to ?? ""}
            onChange={(e) => onChange({ date_to: e.target.value || undefined })}
            aria-label="Hasta"
          />
          <select
            className={selectClass}
            value={filters.sort ?? "recent"}
            onChange={(e) => onChange({ sort: e.target.value as "recent" | "oldest" })}
          >
            <option value="recent">Más recientes</option>
            <option value="oldest">Más antiguos</option>
          </select>
        </div>

        {hasActiveFilters && (
          <div className="flex justify-end">
            <Button type="button" variant="ghost" size="sm" className="gap-1.5" onClick={onReset}>
              <RotateCcw className="h-3.5 w-3.5" />
              Limpiar filtros
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Fila de resultado
// ─────────────────────────────────────────────────────────────────────────────

function ReportRow({ article, onOpen }: { article: ArticleSummary; onOpen: (id: number) => void }) {
  return (
    <Card
      className="cursor-pointer flex-row gap-0 overflow-hidden py-0 transition-colors hover:border-primary/40"
      onClick={() => onOpen(article.id)}
    >
      <span
        className={cn(
          "w-1 flex-none",
          SENTIMENT_BAR_COLOR[article.overall_sentiment ?? "NEU"]
        )}
      />
      <div className="min-w-0 flex-1 space-y-1.5 px-4 py-3">
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <SentimentBadge sentiment={article.overall_sentiment} score={article.sentiment_score} />
          <span>· {formatDate(article.published_at)}</span>
        </div>
        <p className="truncate text-[15px] font-semibold leading-snug">{article.title}</p>
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
          <span>{article.source}</span>
          {article.section && <span>· {article.section}</span>}
          {article.entity_count > 0 && (
            <span>
              · {article.entity_count} {article.entity_count === 1 ? "entidad" : "entidades"}
            </span>
          )}
          {article.main_topic && (
            <span className="rounded-full bg-muted px-2 py-0.5 text-muted-foreground">
              {article.main_topic}
            </span>
          )}
          {article.framing && (
            <span className="rounded-full bg-muted px-2 py-0.5 text-muted-foreground">
              {FRAMING_LABELS[article.framing] ?? article.framing}
            </span>
          )}
          {article.has_hard_data && (
            <span className="rounded-full bg-muted px-2 py-0.5 text-muted-foreground">
              Datos duros
            </span>
          )}
        </div>
      </div>
    </Card>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Formulario de edición (rectificación §8.2)
// ─────────────────────────────────────────────────────────────────────────────

function ArticleEditForm({
  article,
  onSaved,
  onCancel,
}: {
  article: ArticleAnalysis
  onSaved: (updated: ArticleAnalysis) => void
  onCancel: () => void
}) {
  const [form, setForm] = useState<ArticleUpdatePayload>(() => toEditForm(article))
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  function patch(p: Partial<ArticleUpdatePayload>) {
    setForm((f) => ({ ...f, ...p }))
  }

  async function handleSave() {
    setBusy(true)
    setErr(null)
    try {
      const updated = await updateArticle(article.id as number, form)
      onSaved(updated)
    } catch (e) {
      setErr(e instanceof OdinApiError ? e.message : "Error guardando la rectificación.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Rectificar análisis</CardTitle>
        <CardDescription>
          Solo se corrige el análisis (tema, sentimiento, encuadre); título, cuerpo y URL no se
          pueden editar aquí.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {err && (
          <Alert variant="destructive">
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{err}</AlertDescription>
          </Alert>
        )}

        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs text-muted-foreground">Tema principal</label>
            <Input
              value={form.main_topic ?? ""}
              onChange={(e) => patch({ main_topic: e.target.value || null })}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-muted-foreground">
              Palabras clave (separadas por coma)
            </label>
            <Input
              value={form.topic_keywords ?? ""}
              onChange={(e) => patch({ topic_keywords: e.target.value || null })}
            />
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <div>
            <label className="mb-1 block text-xs text-muted-foreground">Sentimiento global</label>
            <select
              className={cn(selectClass, "w-full")}
              value={form.overall_sentiment ?? ""}
              onChange={(e) =>
                patch({ overall_sentiment: (e.target.value || null) as ArticleUpdatePayload["overall_sentiment"] })
              }
            >
              <option value="">—</option>
              {Object.entries(SENTIMENT_LABELS).map(([v, label]) => (
                <option key={v} value={v}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-muted-foreground">Confianza (0–1)</label>
            <Input
              type="number"
              min={0}
              max={1}
              step={0.01}
              value={form.sentiment_score ?? ""}
              onChange={(e) =>
                patch({ sentiment_score: e.target.value === "" ? null : Number(e.target.value) })
              }
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-muted-foreground">Datos duros</label>
            <select
              className={cn(selectClass, "w-full")}
              value={form.has_hard_data == null ? "" : String(form.has_hard_data)}
              onChange={(e) =>
                patch({ has_hard_data: e.target.value === "" ? null : e.target.value === "true" })
              }
            >
              <option value="">—</option>
              <option value="true">Sí</option>
              <option value="false">No</option>
            </select>
          </div>
        </div>

        <Separator />

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <label className="mb-1 block text-xs text-muted-foreground">Encuadre (marco)</label>
            <select
              className={cn(selectClass, "w-full")}
              value={form.framing ?? ""}
              onChange={(e) =>
                patch({ framing: (e.target.value || null) as ArticleUpdatePayload["framing"] })
              }
            >
              <option value="">—</option>
              {Object.entries(FRAMING_LABELS).map(([v, label]) => (
                <option key={v} value={v}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-muted-foreground">Titular</label>
            <select
              className={cn(selectClass, "w-full")}
              value={form.headline_intent ?? ""}
              onChange={(e) =>
                patch({
                  headline_intent: (e.target.value || null) as ArticleUpdatePayload["headline_intent"],
                })
              }
            >
              <option value="">—</option>
              {Object.entries(HEADLINE_LABELS).map(([v, label]) => (
                <option key={v} value={v}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-muted-foreground">Lead</label>
            <select
              className={cn(selectClass, "w-full")}
              value={form.lead_orientation ?? ""}
              onChange={(e) =>
                patch({
                  lead_orientation: (e.target.value || null) as ArticleUpdatePayload["lead_orientation"],
                })
              }
            >
              <option value="">—</option>
              {Object.entries(LEAD_LABELS).map(([v, label]) => (
                <option key={v} value={v}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-muted-foreground">Calidad de fuentes</label>
            <select
              className={cn(selectClass, "w-full")}
              value={form.source_quality ?? ""}
              onChange={(e) =>
                patch({
                  source_quality: (e.target.value || null) as ArticleUpdatePayload["source_quality"],
                })
              }
            >
              <option value="">—</option>
              {Object.entries(SOURCE_LABELS).map(([v, label]) => (
                <option key={v} value={v}>
                  {label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <div>
            <label className="mb-1 block text-xs text-muted-foreground">Actor dominante</label>
            <Input
              value={form.dominant_actor ?? ""}
              onChange={(e) => patch({ dominant_actor: e.target.value || null })}
              placeholder="Debe coincidir con una figura/empresa ya mencionada"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-muted-foreground">Señalado (culpa)</label>
            <Input
              value={form.blamed_actor ?? ""}
              onChange={(e) => patch({ blamed_actor: e.target.value || null })}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-muted-foreground">
              Acreditado (solución)
            </label>
            <Input
              value={form.credited_actor ?? ""}
              onChange={(e) => patch({ credited_actor: e.target.value || null })}
            />
          </div>
        </div>

        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="ghost" size="sm" onClick={onCancel} disabled={busy}>
            Cancelar
          </Button>
          <Button type="button" size="sm" onClick={handleSave} disabled={busy}>
            {busy ? "Guardando…" : "Guardar cambios"}
          </Button>
        </div>
      </CardContent>
    </Card>
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
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    getArticle(id)
      .then((a) => {
        if (!cancelled) setArticle(a)
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e instanceof OdinApiError ? e.message : "No se pudo cargar el reporte.")
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [id])

  async function handleDelete() {
    if (!article) return
    if (!confirm(`¿Eliminar permanentemente el reporte "${article.title}"? No se puede deshacer.`)) {
      return
    }
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

  const keywords = (article?.topic_keywords ?? "")
    .split(",")
    .map((k) => k.trim())
    .filter(Boolean)

  return (
    <div className="w-full space-y-4">
      <div className="flex items-center justify-between">
        <Button type="button" variant="ghost" size="sm" className="gap-1.5" onClick={onBack}>
          <ChevronLeft className="h-3.5 w-3.5" />
          Volver a la lista
        </Button>
        {article && !editing && (
          <div className="flex gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="gap-1.5"
              onClick={() => setEditing(true)}
            >
              <Pencil className="h-3.5 w-3.5" />
              Editar
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="gap-1.5 text-destructive hover:text-destructive"
              disabled={deleting}
              onClick={handleDelete}
            >
              <Trash2 className="h-3.5 w-3.5" />
              {deleting ? "Eliminando…" : "Eliminar"}
            </Button>
          </div>
        )}
      </div>

      {deleteError && (
        <Alert variant="destructive">
          <AlertTitle>No se pudo eliminar</AlertTitle>
          <AlertDescription>{deleteError}</AlertDescription>
        </Alert>
      )}

      {error && (
        <Alert variant="destructive">
          <AlertTitle>No se pudo cargar</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {article && editing && (
        <ArticleEditForm
          article={article}
          onCancel={() => setEditing(false)}
          onSaved={(updated) => {
            setArticle(updated)
            setEditing(false)
          }}
        />
      )}

      {loading && (
        <Card>
          <CardHeader>
            <Skeleton className="h-6 w-3/4" />
            <Skeleton className="mt-2 h-4 w-1/2" />
          </CardHeader>
          <CardContent className="space-y-2">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-2/3" />
          </CardContent>
        </Card>
      )}

      {article && !editing && (
        <>
          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-center gap-2">
                <SentimentBadge sentiment={article.overall_sentiment} score={article.sentiment_score} />
              </div>
              <CardTitle className="text-2xl leading-snug">
                <a href={article.url} target="_blank" rel="noreferrer" className="hover:underline">
                  {article.title}
                </a>
              </CardTitle>
              <CardDescription className="flex flex-wrap gap-x-3 gap-y-1">
                <span>{article.source}</span>
                {article.authors && <span>· {article.authors}</span>}
                {article.section && <span>· {article.section}</span>}
                <span>· {formatDate(article.published_at)}</span>
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <p className="mb-1 text-sm font-medium text-muted-foreground">Tema principal</p>
                <p className="text-lg">{article.main_topic ?? "—"}</p>
              </div>

              {keywords.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {keywords.map((kw) => (
                    <span
                      key={kw}
                      className="rounded-full bg-muted px-2.5 py-0.5 text-xs text-muted-foreground"
                    >
                      {kw}
                    </span>
                  ))}
                </div>
              )}

              {article.framing != null && (
                <>
                  <Separator />
                  <div>
                    <p className="mb-2 text-sm font-medium text-muted-foreground">
                      Análisis de encuadre
                    </p>
                    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                      {(
                        [
                          ["Marco", article.framing, FRAMING_LABELS],
                          ["Titular", article.headline_intent, HEADLINE_LABELS],
                          ["Lead", article.lead_orientation, LEAD_LABELS],
                          ["Fuentes", article.source_quality, SOURCE_LABELS],
                        ] as const
                      ).map(([label, value, labels]) => (
                        <div key={label}>
                          <p className="mb-1 text-xs text-muted-foreground">{label}</p>
                          <span className="inline-block rounded-full bg-muted px-2.5 py-0.5 text-xs">
                            {value ? labels[value] ?? value : "—"}
                          </span>
                        </div>
                      ))}
                    </div>
                    <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                      {(
                        [
                          ["Actor dominante", article.dominant_actor],
                          ["Señalado (culpa)", article.blamed_actor],
                          ["Acreditado (solución)", article.credited_actor],
                        ] as const
                      ).map(([label, value]) => (
                        <div key={label}>
                          <p className="mb-1 text-xs text-muted-foreground">{label}</p>
                          <p className="text-sm">{value ?? "—"}</p>
                        </div>
                      ))}
                      <div>
                        <p className="mb-1 text-xs text-muted-foreground">Datos duros</p>
                        <span className="inline-block rounded-full bg-muted px-2.5 py-0.5 text-xs">
                          {article.has_hard_data == null ? "—" : article.has_hard_data ? "Sí" : "No"}
                        </span>
                      </div>
                    </div>
                  </div>
                </>
              )}

              <Separator />
              <div>
                <p className="mb-1 text-sm font-medium text-muted-foreground">Cuerpo del artículo</p>
                <p className="max-h-64 overflow-y-auto whitespace-pre-line text-sm leading-relaxed text-foreground/90">
                  {article.body}
                </p>
              </div>
            </CardContent>
          </Card>

          <div>
            <h2 className="mb-3 text-lg font-medium">
              Figuras y empresas mencionadas
              {article.entities.length > 0 && (
                <span className="ml-2 text-sm font-normal text-muted-foreground">
                  ({article.entities.length})
                </span>
              )}
            </h2>
            {article.entities.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No se detectaron figuras públicas ni empresas en este artículo.
              </p>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2">
                {article.entities.map((ent) => (
                  <Card key={`${ent.type}-${ent.name}`} className="gap-3 py-4">
                    <CardHeader className="px-4">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <CardTitle className="flex items-center gap-1.5 text-base">
                            {ent.name}
                            {isLowConfidence(ent) && (
                              <AlertTriangle
                                className="h-3.5 w-3.5 shrink-0 text-amber-600 dark:text-amber-400"
                                aria-label="Confianza de extracción baja"
                              >
                                <title>Confianza de extracción baja: revisa si el nombre/tipo es correcto.</title>
                              </AlertTriangle>
                            )}
                          </CardTitle>
                          <CardDescription>
                            {ent.type === "PERSON" ? "Persona" : "Organización"}
                            {" · "}
                            {ent.mentions_count} {ent.mentions_count === 1 ? "mención" : "menciones"}
                          </CardDescription>
                        </div>
                        <SentimentBadge sentiment={ent.sentiment_toward} score={ent.sentiment_score} />
                      </div>
                    </CardHeader>
                    {ent.context && (
                      <CardContent className="px-4">
                        <p className="text-xs text-muted-foreground italic">“{ent.context}”</p>
                      </CardContent>
                    )}
                  </Card>
                ))}
              </div>
            )}
          </div>
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

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await listArticles({
        ...filters,
        has_hard_data: hardData === "" ? undefined : hardData === "true",
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      })
      setData(res)
    } catch (e) {
      setError(
        e instanceof OdinApiError ? e.message : "No se pudo conectar con la API de Odin."
      )
    } finally {
      setLoading(false)
    }
  }, [filters, hardData, page])

  useEffect(() => {
    const t = setTimeout(load, 300)
    return () => clearTimeout(t)
  }, [load])

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
    hardData !== "" ||
    Object.entries(filters).some(([k, v]) => k !== "sort" && v !== undefined && v !== "")

  const total = data?.total ?? 0
  const items = data?.items ?? []
  const from = total === 0 ? 0 : page * PAGE_SIZE + 1
  const to = Math.min(total, (page + 1) * PAGE_SIZE)

  if (selectedId != null) {
    return <ReportDetail id={selectedId} onBack={() => setSelectedId(null)} />
  }

  return (
    <div className="w-full space-y-4">
      <FilterBar
        filters={filters}
        onChange={updateFilters}
        hardData={hardData}
        onHardDataChange={updateHardData}
        facets={facets}
        onReset={resetFilters}
        hasActiveFilters={hasActiveFilters}
      />

      {error && (
        <Alert variant="destructive">
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>
          {loading
            ? "Cargando…"
            : total === 0
              ? "Sin resultados"
              : `${from}–${to} de ${total} reportes`}
        </span>
        {hasActiveFilters && !loading && (
          <button
            type="button"
            onClick={resetFilters}
            className="flex items-center gap-1 hover:text-foreground"
          >
            <X className="h-3.5 w-3.5" />
            Quitar filtros
          </button>
        )}
      </div>

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i} className="py-4">
              <CardHeader className="px-4">
                <Skeleton className="h-5 w-2/3" />
                <Skeleton className="mt-2 h-3.5 w-1/3" />
              </CardHeader>
            </Card>
          ))}
        </div>
      ) : items.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center text-sm text-muted-foreground">
            No hay reportes que coincidan con estos filtros.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {items.map((a) => (
            <ReportRow key={a.id} article={a} onOpen={setSelectedId} />
          ))}
        </div>
      )}

      {total > PAGE_SIZE && (
        <div className="flex items-center justify-center gap-3 pt-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={page === 0 || loading}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            className="gap-1"
          >
            <ChevronLeft className="h-3.5 w-3.5" />
            Anterior
          </Button>
          <span className={cn("text-sm text-muted-foreground")}>
            Página {page + 1} de {Math.max(1, Math.ceil(total / PAGE_SIZE))}
          </span>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={to >= total || loading}
            onClick={() => setPage((p) => p + 1)}
            className="gap-1"
          >
            Siguiente
            <ChevronRight className="h-3.5 w-3.5" />
          </Button>
        </div>
      )}
    </div>
  )
}
