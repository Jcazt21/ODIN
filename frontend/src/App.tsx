import { useEffect, useState, type FormEvent } from "react"
import { LogOut, X } from "lucide-react"
import { Aurora } from "@/components/Aurora"
import { PillNav } from "@/components/PillNav"
import { SentimentBadge } from "@/components/SentimentBadge"
import { SentimentSegmented } from "@/components/SentimentSegmented"
import { AliasManager } from "@/components/AliasManager"
import { CanonicalEntityManager } from "@/components/CanonicalEntityManager"
import { ReportsList } from "@/components/ReportsList"
import { LoginScreen } from "@/components/LoginScreen"
import { Button } from "@/components/ui/button"
import { InteractiveHoverButton } from "@/components/ui/interactive-hover-button"
import { ShimmerText } from "@/components/ui/shimmer-text"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { cn } from "@/lib/utils"
import {
  analyzeUrl,
  getMe,
  saveArticle,
  OdinApiError,
  type ArticleAnalysis,
  type EntityAnalysis,
  type SaveArticlePayload,
} from "@/lib/odin-api"
import { AUTH_EXPIRED_EVENT, clearSession, getToken, getUsername } from "@/lib/auth"

// Fuera del componente: una referencia estable evita que el efecto de layout
// de PillNav se re-ejecute en cada render de App.
const NAV_ITEMS = [
  { label: "Analizar",   tab: "analyze" },
  { label: "Reportes",   tab: "reports" },
  { label: "Entidades",  tab: "entities" },
  { label: "Siglas",     tab: "aliases" },
]

// Etiquetas legibles para el análisis de encuadre (valores del backend)
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

function isLowConfidence(e: EntityAnalysis) {
  return typeof e.extraction_confidence === "number" && e.extraction_confidence < 0.9
}

function toDraft(a: ArticleAnalysis): SaveArticlePayload {
  const {
    id: _id,
    already_saved: _saved,
    analyzer_name: _an,
    analyzer_model: _am,
    analyzer_version: _av,
    analysis_schema_version: _asv,
    analyzed_at: _at,
    ...rest
  } = a
  return { ...rest, entities: a.entities.map((e) => ({ ...e })) }
}

function EntityGroup({
  label,
  count,
  items,
  isDraft,
  onUpdate,
  onRemove,
}: {
  label: string
  count: number
  items: { e: EntityAnalysis; i: number }[]
  isDraft: boolean
  onUpdate: (index: number, patch: Partial<EntityAnalysis>) => void
  onRemove: (index: number) => void
}) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2.5">
        <span className="text-xs font-bold tracking-wide text-muted-foreground uppercase">
          {label}
        </span>
        <span className="h-px flex-1 bg-border" />
        <span className="font-mono text-xs text-muted-foreground">{count}</span>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {items.map(({ e: ent, i }) => (
          <Card
            key={isDraft ? i : `${ent.type}-${ent.name}`}
            className={cn(
              "gap-0 overflow-hidden py-0",
              isDraft && isLowConfidence(ent) && "border-warning/45"
            )}
          >
            {isDraft && isLowConfidence(ent) && (
              <div className="flex items-center gap-1.5 border-b border-warning/25 bg-warning/10 px-4 py-1.5 text-[11.5px] font-semibold text-warning">
                <span className="size-1.5 rounded-full bg-warning" />
                Revisar — baja confianza en la clasificación
              </div>
            )}
            <div className="space-y-3 p-4">
              <div className="flex items-center gap-2">
                {isDraft ? (
                  <Input
                    value={ent.name}
                    onChange={(e) => onUpdate(i, { name: e.target.value })}
                    className="h-8 flex-1 font-medium"
                  />
                ) : (
                  <span className="flex-1 text-[15px] font-semibold">{ent.name}</span>
                )}
                {isDraft && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    aria-label="Eliminar entidad"
                    className="text-muted-foreground hover:text-destructive"
                    onClick={() => onRemove(i)}
                  >
                    <X />
                  </Button>
                )}
              </div>

              <div className="flex flex-wrap items-center gap-2">
                {isDraft ? (
                  <select
                    className={cn(selectClass, "h-7 text-xs")}
                    value={ent.type}
                    onChange={(e) => onUpdate(i, { type: e.target.value })}
                  >
                    <option value="PERSON">Persona</option>
                    <option value="ORG">Organización</option>
                  </select>
                ) : (
                  <span className="rounded-md border border-border bg-muted px-2 py-0.5 text-[11.5px] text-muted-foreground">
                    {ent.type === "PERSON" ? "Persona" : "Organización"}
                  </span>
                )}
                <span className="font-mono text-[11.5px] text-muted-foreground">
                  {ent.mentions_count} {ent.mentions_count === 1 ? "menc." : "menc."}
                </span>
                <span className="flex-1" />
                {isDraft ? (
                  <SentimentSegmented
                    value={ent.sentiment_toward ?? "NEU"}
                    onChange={(v) => onUpdate(i, { sentiment_toward: v })}
                    size="sm"
                  />
                ) : (
                  <SentimentBadge sentiment={ent.sentiment_toward} score={ent.sentiment_score} />
                )}
              </div>

              {ent.context && (
                <blockquote className="border-l-2 border-border pl-3 font-serif text-[13.5px] leading-snug text-muted-foreground italic text-pretty">
                  “{ent.context}”
                </blockquote>
              )}
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}

interface WorkspaceProps {
  onLogout: () => void
}

function Workspace({ onLogout }: WorkspaceProps) {
  const [tab, setTab] = useState<"analyze" | "reports" | "entities" | "aliases">("analyze")
  const [url, setUrl] = useState("")
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<ArticleAnalysis | null>(null)
  const [draft, setDraft] = useState<SaveArticlePayload | null>(null)
  const [entityFilter, setEntityFilter] = useState<"all" | "PERSON" | "ORG">("all")

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!url.trim() || loading) return
    setLoading(true)
    setError(null)
    setResult(null)
    setDraft(null)
    setEntityFilter("all")
    try {
      const data = await analyzeUrl(url.trim())
      setResult(data)
      if (!data.already_saved) setDraft(toDraft(data))
    } catch (err) {
      setError(
        err instanceof OdinApiError
          ? err.message
          : "No se pudo conectar con la API de Odin. ¿Está corriendo en el puerto 8000?"
      )
    } finally {
      setLoading(false)
    }
  }

  async function handleSave() {
    if (!draft || saving) return
    setSaving(true)
    setError(null)
    try {
      const saved = await saveArticle(draft)
      setResult(saved)
      setDraft(null)
    } catch (err) {
      setError(
        err instanceof OdinApiError ? err.message : "No se pudo guardar el artículo."
      )
    } finally {
      setSaving(false)
    }
  }

  function updateEntity(index: number, patch: Partial<EntityAnalysis>) {
    setDraft((d) => {
      if (!d) return d
      const entities = d.entities.map((e, i) => (i === index ? { ...e, ...patch } : e))
      return { ...d, entities }
    })
  }

  function removeEntity(index: number) {
    setDraft((d) => {
      if (!d) return d
      return { ...d, entities: d.entities.filter((_, i) => i !== index) }
    })
  }

  function removeKeyword(index: number) {
    setDraft((d) => {
      if (!d) return d
      const kws = (d.topic_keywords ?? "")
        .split(",")
        .map((k) => k.trim())
        .filter(Boolean)
      kws.splice(index, 1)
      return { ...d, topic_keywords: kws.join(", ") || null }
    })
  }

  function addKeyword(text: string) {
    const v = text.trim()
    if (!v) return
    setDraft((d) => {
      if (!d) return d
      const kws = (d.topic_keywords ?? "")
        .split(",")
        .map((k) => k.trim())
        .filter(Boolean)
      kws.push(v)
      return { ...d, topic_keywords: kws.join(", ") }
    })
  }

  const view = result
  const isDraft = draft !== null
  const keywordsText = isDraft ? draft.topic_keywords ?? "" : view?.topic_keywords ?? ""
  const keywords = keywordsText
    .split(",")
    .map((k) => k.trim())
    .filter(Boolean)
  const entities = isDraft ? draft.entities : view?.entities ?? []
  const entitiesWithIndex = entities.map((e, i) => ({ e, i }))
  const personEntities = entitiesWithIndex.filter(({ e }) => e.type === "PERSON")
  const orgEntities = entitiesWithIndex.filter(({ e }) => e.type !== "PERSON")
  const lowConfidenceCount = entities.filter(isLowConfidence).length

  return (
    <div className="relative min-h-screen">
      <Aurora />

      {/* ── PillNav ────────────────────────────────────────────────── */}
      <PillNav
        wordmark="ODIN"
        activeTab={tab}
        onTabChange={(t) => setTab(t as "analyze" | "reports" | "entities" | "aliases")}
        items={NAV_ITEMS}
        initialLoadAnimation
      />

      {/* Cerrar sesión — alineado con la altura del PillNav (top: 1.1em) */}
      <Button
        type="button"
        variant="ghost"
        size="icon"
        onClick={onLogout}
        title="Cerrar sesión"
        aria-label="Cerrar sesión"
        className="fixed right-4 top-[1.1em] z-[99] size-11 rounded-full text-muted-foreground hover:text-foreground"
      >
        <LogOut />
      </Button>

      <main
        className={cn(
          "mx-auto flex flex-col items-center gap-8 px-4 pt-28 pb-16",
          tab === "reports" || tab === "entities" ? "max-w-5xl" : "max-w-3xl"
        )}
      >

        {/* ── Tab: Analizar ─────────────────────────────────────────── */}
        {tab === "analyze" && (
          <div className="flex w-full flex-col items-center gap-8">
            <div className="flex flex-col items-center text-center">
              <ShimmerText className="text-6xl font-bold tracking-tighter sm:text-8xl">
                ODIN
              </ShimmerText>
            </div>

            <form onSubmit={handleSubmit} className="flex w-full max-w-2xl gap-2">
              <Input
                type="url"
                required
                placeholder="https://listindiario.com/..."
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                className="h-11 flex-1"
              />
              <InteractiveHoverButton
                type="submit"
                disabled={loading}
                loading={loading}
                text={loading ? "Analizando…" : "Analizar"}
              />
            </form>

        {error && (
          <Alert variant="destructive" className="w-full">
            <AlertTitle>No se pudo analizar</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {loading && (
          <Card className="w-full">
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

        {view && (
          <div className="w-full space-y-5">
            <Card className="gap-0 overflow-hidden py-0">
              {!view.already_saved && (
                <div className="flex flex-wrap items-center gap-2.5 border-b border-warning/25 bg-warning/10 px-6 py-3">
                  <span className="inline-flex items-center gap-1.5 rounded-md border border-warning/40 bg-warning/15 px-2 py-0.5 font-mono text-[11px] font-bold tracking-wider text-warning">
                    VISTA PREVIA
                  </span>
                  <span className="text-[13px] text-muted-foreground">
                    Aún no guardado — revisa, corrige y guarda para persistir en la base de
                    datos.
                  </span>
                </div>
              )}

              <CardContent className="space-y-6 p-6">
                {/* Título + sentimiento global */}
                <div className="flex flex-wrap items-start justify-between gap-6">
                  <div className="min-w-0 flex-1 space-y-3">
                    <h1 className="text-2xl leading-tight font-semibold text-balance font-serif">
                      <a href={view.url} target="_blank" rel="noreferrer" className="hover:underline">
                        {view.title}
                      </a>
                    </h1>
                    <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1 font-mono text-[12.5px] text-muted-foreground">
                      <span className="inline-flex items-center gap-1.5">
                        <span className="size-1.5 rounded-full bg-muted-foreground/60" />
                        {view.source}
                      </span>
                      {view.authors && (
                        <>
                          <span className="text-muted-foreground/40">·</span>
                          <span>{view.authors}</span>
                        </>
                      )}
                      {view.section && (
                        <>
                          <span className="text-muted-foreground/40">·</span>
                          <span>{view.section}</span>
                        </>
                      )}
                      <span className="text-muted-foreground/40">·</span>
                      <span>{formatDate(view.published_at)}</span>
                    </div>
                  </div>

                  <div className="w-full flex-none space-y-2.5 rounded-xl border border-border bg-muted/30 p-4 sm:w-48">
                    <p className="text-[10.5px] font-semibold tracking-wide text-muted-foreground uppercase">
                      Sentimiento global
                    </p>
                    {isDraft ? (
                      <SentimentSegmented
                        value={draft.overall_sentiment ?? "NEU"}
                        onChange={(v) =>
                          setDraft((d) => (d ? { ...d, overall_sentiment: v } : d))
                        }
                      />
                    ) : (
                      <SentimentBadge sentiment={view.overall_sentiment} />
                    )}
                    {typeof view.sentiment_score === "number" && (
                      <div className="space-y-1">
                        <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                          <span>Confianza</span>
                          <span className="font-mono text-foreground/80">
                            {Math.round(view.sentiment_score * 100)}%
                          </span>
                        </div>
                        <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                          <div
                            className="h-full rounded-full bg-muted-foreground/70"
                            style={{ width: `${Math.round(view.sentiment_score * 100)}%` }}
                          />
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Campos editables / encuadre */}
                <div className="space-y-4 border-t border-border pt-5">
                  <div className="space-y-1.5">
                    <label className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
                      Tema principal
                    </label>
                    {isDraft ? (
                      <Input
                        value={draft.main_topic ?? ""}
                        onChange={(e) =>
                          setDraft((d) => (d ? { ...d, main_topic: e.target.value || null } : d))
                        }
                      />
                    ) : (
                      <p className="text-lg">{view.main_topic ?? "—"}</p>
                    )}
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
                      Palabras clave
                    </label>
                    {isDraft ? (
                      <div className="flex flex-wrap items-center gap-1.5 rounded-lg border border-input bg-muted/30 p-2">
                        {keywords.map((kw, i) => (
                          <span
                            key={`${kw}-${i}`}
                            className="inline-flex items-center gap-1 rounded-md border border-border bg-background py-1 pr-1 pl-2.5 text-[13px]"
                          >
                            {kw}
                            <button
                              type="button"
                              onClick={() => removeKeyword(i)}
                              aria-label={`Quitar ${kw}`}
                              className="inline-flex size-4 items-center justify-center rounded text-muted-foreground hover:bg-destructive/15 hover:text-destructive"
                            >
                              <X className="size-3" />
                            </button>
                          </span>
                        ))}
                        <input
                          placeholder="añadir…"
                          onKeyDown={(e) => {
                            if (e.key !== "Enter") return
                            e.preventDefault()
                            addKeyword(e.currentTarget.value)
                            e.currentTarget.value = ""
                          }}
                          className="min-w-[90px] flex-1 bg-transparent px-1 py-1 text-[13px] outline-none"
                        />
                      </div>
                    ) : (
                      keywords.length > 0 && (
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
                      )
                    )}
                  </div>
                </div>

                {(isDraft ? draft.framing : view.framing) != null && (
                  <>
                    <Separator />
                    <div>
                      <p className="mb-2 text-sm font-medium text-muted-foreground">
                        Análisis de encuadre
                      </p>
                      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                        {(
                          [
                            ["Marco", "framing", FRAMING_LABELS],
                            ["Titular", "headline_intent", HEADLINE_LABELS],
                            ["Lead", "lead_orientation", LEAD_LABELS],
                            ["Fuentes", "source_quality", SOURCE_LABELS],
                          ] as const
                        ).map(([label, field, labels]) => {
                          const value = (isDraft ? draft : view)[field]
                          return (
                            <div key={field}>
                              <p className="mb-1 text-xs text-muted-foreground">{label}</p>
                              {isDraft ? (
                                <select
                                  className={selectClass}
                                  value={value ?? ""}
                                  onChange={(e) =>
                                    setDraft((d) =>
                                      d ? { ...d, [field]: e.target.value || null } : d
                                    )
                                  }
                                >
                                  {Object.entries(labels).map(([v, l]) => (
                                    <option key={v} value={v}>
                                      {l}
                                    </option>
                                  ))}
                                </select>
                              ) : (
                                <span className="inline-block rounded-full bg-muted px-2.5 py-0.5 text-xs">
                                  {value ? labels[value] ?? value : "—"}
                                </span>
                              )}
                            </div>
                          )
                        })}
                      </div>
                      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                        {(
                          [
                            ["Actor dominante", "dominant_actor"],
                            ["Señalado (culpa)", "blamed_actor"],
                            ["Acreditado (solución)", "credited_actor"],
                          ] as const
                        ).map(([label, field]) => {
                          const value = (isDraft ? draft : view)[field]
                          return (
                            <div key={field}>
                              <p className="mb-1 text-xs text-muted-foreground">{label}</p>
                              {isDraft ? (
                                <Input
                                  className="h-8"
                                  value={value ?? ""}
                                  onChange={(e) =>
                                    setDraft((d) =>
                                      d ? { ...d, [field]: e.target.value || null } : d
                                    )
                                  }
                                />
                              ) : (
                                <p className="text-sm">{value ?? "—"}</p>
                              )}
                            </div>
                          )
                        })}
                        <div>
                          <p className="mb-1 text-xs text-muted-foreground">Datos duros</p>
                          <span className="inline-block rounded-full bg-muted px-2.5 py-0.5 text-xs">
                            {(isDraft ? draft : view).has_hard_data == null
                              ? "—"
                              : (isDraft ? draft : view).has_hard_data
                                ? "Sí"
                                : "No"}
                          </span>
                        </div>
                      </div>
                    </div>
                  </>
                )}

                <Separator />
                <div className="space-y-1.5">
                  <label className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
                    Cuerpo del artículo
                  </label>
                  <div className="max-h-64 overflow-y-auto rounded-lg border border-border bg-muted/20 p-4">
                    {view.body
                      .split(/\n+/)
                      .map((p) => p.trim())
                      .filter(Boolean)
                      .map((p, i) => (
                        <p
                          key={i}
                          className="font-serif text-[15px] leading-relaxed text-foreground/85 text-pretty last:mb-0"
                          style={{ marginBottom: "0.8em" }}
                        >
                          {p}
                        </p>
                      ))}
                  </div>
                </div>
              </CardContent>

              {isDraft && (
                <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-6 py-4">
                  <span className="text-[12.5px] text-muted-foreground">
                    Los cambios se guardan tal como los edites.
                  </span>
                  <div className="flex items-center gap-2.5">
                    <Button
                      type="button"
                      variant="outline"
                      className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                      onClick={() => {
                        setResult(null)
                        setDraft(null)
                      }}
                    >
                      Descartar
                    </Button>
                    <Button type="button" disabled={saving} onClick={handleSave}>
                      {saving ? "Guardando…" : "Guardar en base de datos"}
                    </Button>
                  </div>
                </div>
              )}
            </Card>

            <div className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-baseline gap-3">
                  <h2 className="text-lg font-semibold">Entidades mencionadas</h2>
                  <span className="font-mono text-sm text-muted-foreground">
                    {entities.length}
                  </span>
                  {isDraft && lowConfidenceCount > 0 && (
                    <span className="inline-flex items-center gap-1.5 rounded-full border border-warning/40 bg-warning/15 px-2.5 py-0.5 text-xs font-semibold text-warning">
                      <span className="size-1.5 rounded-full bg-warning" />
                      {lowConfidenceCount} por revisar
                    </span>
                  )}
                </div>
                <div className="inline-flex gap-0.5 rounded-lg border border-border bg-muted/40 p-0.5">
                  {(
                    [
                      ["all", "Todas"],
                      ["PERSON", "Personas"],
                      ["ORG", "Organizaciones"],
                    ] as const
                  ).map(([value, label]) => (
                    <button
                      key={value}
                      type="button"
                      onClick={() => setEntityFilter(value)}
                      className={cn(
                        "rounded-[7px] px-3.5 py-1.5 text-[13px] font-medium transition-colors",
                        entityFilter === value
                          ? "bg-background text-foreground shadow-sm"
                          : "text-muted-foreground hover:text-foreground"
                      )}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>

              {entities.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No se detectaron figuras públicas ni empresas en este artículo.
                </p>
              ) : (
                <>
                  {personEntities.length > 0 && entityFilter !== "ORG" && (
                    <EntityGroup
                      label="Personas"
                      count={personEntities.length}
                      items={personEntities}
                      isDraft={isDraft}
                      onUpdate={updateEntity}
                      onRemove={removeEntity}
                    />
                  )}
                  {orgEntities.length > 0 && entityFilter !== "PERSON" && (
                    <EntityGroup
                      label="Empresas y organizaciones"
                      count={orgEntities.length}
                      items={orgEntities}
                      isDraft={isDraft}
                      onUpdate={updateEntity}
                      onRemove={removeEntity}
                    />
                  )}
                </>
              )}
            </div>
          </div>
        )}
          </div>
        )}

        {/* ── Tab: Reportes ─────────────────────────────────────────── */}
        {tab === "reports" && <ReportsList />}

        {/* ── Tab: Entidades canónicas ─────────────────────────────── */}
        {tab === "entities" && <CanonicalEntityManager />}

        {/* ── Tab: Siglas ────────────────────────────────────────────── */}
        {tab === "aliases" && <AliasManager />}
      </main>
    </div>
  )
}

/**
 * Puerta de entrada: sin sesión válida no se monta nada del workspace.
 *
 * Al abrir la aplicación con un token guardado lo validamos contra
 * /api/auth/me — puede haber vencido o haber sido firmado con otro secreto
 * (la API reinició sin ODIN_JWT_SECRET). Mientras tanto se muestra solo el
 * fondo, para no parpadear entre login y workspace.
 */
function App() {
  const [username, setUsername] = useState<string | null>(() =>
    getToken() ? getUsername() : null
  )
  const [checking, setChecking] = useState(() => Boolean(getToken()))

  // Cualquier 401 en cualquier llamada devuelve al login.
  useEffect(() => {
    const onExpired = () => setUsername(null)
    window.addEventListener(AUTH_EXPIRED_EVENT, onExpired)
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired)
  }, [])

  useEffect(() => {
    if (!getToken()) return
    let alive = true
    getMe()
      .then((me) => alive && setUsername(me.username))
      .catch(() => alive && setUsername(null)) // el 401 ya limpió el token
      .finally(() => alive && setChecking(false))
    return () => {
      alive = false
    }
  }, [])

  function handleLogout() {
    clearSession()
    setUsername(null)
  }

  if (checking) {
    return (
      <div className="relative min-h-screen">
        <Aurora />
      </div>
    )
  }

  if (!username) {
    return <LoginScreen onSuccess={setUsername} />
  }

  return <Workspace onLogout={handleLogout} />
}

export default App
