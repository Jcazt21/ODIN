import { useEffect, useState, type FormEvent } from "react"
import { LogOut, X, AlertTriangle } from "lucide-react"
import { Aurora } from "@/components/Aurora"
import { PillNav } from "@/components/PillNav"
import { SentimentBadge } from "@/components/SentimentBadge"
import { AliasManager } from "@/components/AliasManager"
import { CanonicalEntityManager } from "@/components/CanonicalEntityManager"
import { ReportsList } from "@/components/ReportsList"
import { LoginScreen } from "@/components/LoginScreen"
import { Button } from "@/components/ui/button"
import { InteractiveHoverButton } from "@/components/ui/interactive-hover-button"
import { ShimmerText } from "@/components/ui/shimmer-text"
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

const SENTIMENTS = ["POS", "NEG", "NEU"] as const

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
  const { id: _id, already_saved: _saved, ...rest } = a
  return { ...rest, entities: a.entities.map((e) => ({ ...e })) }
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

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!url.trim() || loading) return
    setLoading(true)
    setError(null)
    setResult(null)
    setDraft(null)
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

  const view = result
  const isDraft = draft !== null
  const keywordsText = isDraft ? draft.topic_keywords ?? "" : view?.topic_keywords ?? ""
  const keywords = keywordsText
    .split(",")
    .map((k) => k.trim())
    .filter(Boolean)
  const entities = isDraft ? draft.entities : view?.entities ?? []

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
          <div className="w-full space-y-6">
            <Card>
              <CardHeader>
                <div className="flex flex-wrap items-center gap-2">
                  <SentimentBadge
                    sentiment={view.overall_sentiment}
                    score={view.sentiment_score}
                  />
                  {view.already_saved ? (
                    <span className="text-xs text-muted-foreground">
                      ya estaba guardada en la base de datos
                    </span>
                  ) : (
                    <span className="text-xs text-warning">
                      vista previa · revisa y guarda para persistirla
                    </span>
                  )}
                </div>
                <CardTitle className="text-2xl leading-snug">
                  <a
                    href={view.url}
                    target="_blank"
                    rel="noreferrer"
                    className="hover:underline"
                  >
                    {view.title}
                  </a>
                </CardTitle>
                <CardDescription className="flex flex-wrap gap-x-3 gap-y-1">
                  <span>{view.source}</span>
                  {view.authors && <span>· {view.authors}</span>}
                  {view.section && <span>· {view.section}</span>}
                  <span>· {formatDate(view.published_at)}</span>
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-4 sm:grid-cols-[1fr_auto]">
                  <div>
                    <p className="mb-1 text-sm font-medium text-muted-foreground">
                      Tema principal
                    </p>
                    {isDraft ? (
                      <Input
                        value={draft.main_topic ?? ""}
                        onChange={(e) =>
                          setDraft((d) =>
                            d ? { ...d, main_topic: e.target.value || null } : d
                          )
                        }
                      />
                    ) : (
                      <p className="text-lg">{view.main_topic ?? "—"}</p>
                    )}
                  </div>
                  {isDraft && (
                    <div>
                      <p className="mb-1 text-sm font-medium text-muted-foreground">
                        Sentimiento global
                      </p>
                      <select
                        className={selectClass}
                        value={draft.overall_sentiment ?? "NEU"}
                        onChange={(e) =>
                          setDraft((d) =>
                            d
                              ? {
                                  ...d,
                                  overall_sentiment:
                                    e.target.value as (typeof SENTIMENTS)[number],
                                }
                              : d
                          )
                        }
                      >
                        {SENTIMENTS.map((s) => (
                          <option key={s} value={s}>
                            {s}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}
                </div>

                {isDraft ? (
                  <div>
                    <p className="mb-1 text-sm font-medium text-muted-foreground">
                      Palabras clave (separadas por coma)
                    </p>
                    <Input
                      value={draft.topic_keywords ?? ""}
                      onChange={(e) =>
                        setDraft((d) =>
                          d ? { ...d, topic_keywords: e.target.value || null } : d
                        )
                      }
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
                <div>
                  <p className="mb-1 text-sm font-medium text-muted-foreground">
                    Cuerpo del artículo
                  </p>
                  <p className="max-h-64 overflow-y-auto whitespace-pre-line text-sm leading-relaxed text-foreground/90">
                    {view.body}
                  </p>
                </div>
              </CardContent>
            </Card>

            <div>
              <h2 className="mb-3 text-lg font-medium">
                Figuras y empresas mencionadas
                {entities.length > 0 && (
                  <span className="ml-2 text-sm font-normal text-muted-foreground">
                    ({entities.length})
                  </span>
                )}
              </h2>

              {entities.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No se detectaron figuras públicas ni empresas en este artículo.
                </p>
              ) : (
                <div className="grid gap-3 sm:grid-cols-2">
                  {entities.map((ent, i) => (
                    <Card
                      key={isDraft ? i : `${ent.type}-${ent.name}`}
                      className="gap-3 py-4"
                    >
                      <CardHeader className="px-4">
                        <div className="flex items-start justify-between gap-2">
                          {isDraft ? (
                            <div className="flex-1 space-y-1.5">
                              <Input
                                value={ent.name}
                                onChange={(e) =>
                                  updateEntity(i, { name: e.target.value })
                                }
                                className="font-medium"
                              />
                              <div className="flex items-center gap-1.5">
                                <select
                                  className={cn(selectClass, "h-7 text-xs")}
                                  value={ent.type}
                                  onChange={(e) =>
                                    updateEntity(i, { type: e.target.value })
                                  }
                                >
                                  <option value="PERSON">Persona</option>
                                  <option value="ORG">Organización</option>
                                </select>
                                <span className="text-xs text-muted-foreground">
                                  {ent.mentions_count}{" "}
                                  {ent.mentions_count === 1 ? "mención" : "menciones"}
                                </span>
                                {isLowConfidence(ent) && (
                                  <span
                                    className="flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400"
                                    title="Confianza de extracción baja: revisa si el nombre/tipo es correcto."
                                  >
                                    <AlertTriangle className="h-3 w-3" />
                                    revisar
                                  </span>
                                )}
                              </div>
                            </div>
                          ) : (
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
                                {ent.mentions_count}{" "}
                                {ent.mentions_count === 1 ? "mención" : "menciones"}
                              </CardDescription>
                            </div>
                          )}

                          {isDraft ? (
                            <div className="flex items-center gap-1">
                              <select
                                className={cn(selectClass, "h-7 text-xs")}
                                value={ent.sentiment_toward ?? "NEU"}
                                onChange={(e) =>
                                  updateEntity(i, {
                                    sentiment_toward:
                                      e.target.value as EntityAnalysis["sentiment_toward"],
                                  })
                                }
                              >
                                {SENTIMENTS.map((s) => (
                                  <option key={s} value={s}>
                                    {s}
                                  </option>
                                ))}
                              </select>
                              <Button
                                type="button"
                                variant="ghost"
                                size="icon-sm"
                                aria-label="Eliminar entidad"
                                onClick={() => removeEntity(i)}
                              >
                                <X />
                              </Button>
                            </div>
                          ) : (
                            <SentimentBadge
                              sentiment={ent.sentiment_toward}
                              score={ent.sentiment_score}
                            />
                          )}
                        </div>
                      </CardHeader>
                      {ent.context && (
                        <CardContent className="px-4">
                          <p className="text-xs text-muted-foreground italic">
                            “{ent.context}”
                          </p>
                        </CardContent>
                      )}
                    </Card>
                  ))}
                </div>
              )}
            </div>

            {isDraft && (
              <div className="flex justify-end">
                <Button type="button" size="lg" disabled={saving} onClick={handleSave}>
                  {saving ? "Guardando…" : "Guardar cambios"}
                </Button>
              </div>
            )}
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
