import { useEffect, useState, type FormEvent } from "react"
import { Nav } from "@/components/Nav"
import { Aurora } from "@/components/Aurora"
import { AnalysisCard, type AnalysisCardFields } from "@/components/AnalysisCard"
import { EntitiesCard } from "@/components/EntitiesCard"
import { AliasManager } from "@/components/AliasManager"
import { CanonicalEntityManager } from "@/components/CanonicalEntityManager"
import { ReportsList } from "@/components/ReportsList"
import { ScrapeTab } from "@/components/ScrapeTab"
import { LoginScreen } from "@/components/LoginScreen"
import { DialogProvider } from "@/lib/dialog"
import {
  analyzeUrl,
  getMe,
  saveArticle,
  OdinApiError,
  type ArticleAnalysis,
  type EntityAnalysis,
  type JobStatus,
  type SaveArticlePayload,
} from "@/lib/odin-api"
import { AUTH_EXPIRED_EVENT, clearSession, getToken, getUsername } from "@/lib/auth"

type Theme = "light" | "dark"
const THEME_KEY = "odin.theme"

function getInitialTheme(): Theme {
  try {
    const stored = localStorage.getItem(THEME_KEY)
    if (stored === "light" || stored === "dark") return stored
  } catch {
    // localStorage no disponible: usar el default
  }
  return "light"
}

const NAV_ITEMS = [
  { label: "Analizar", tab: "analyze" },
  { label: "Reportes", tab: "reports" },
  { label: "Entidades", tab: "entities" },
  { label: "Siglas", tab: "aliases" },
  { label: "Scraper", tab: "scrape" },
]

// Apaga la banda de Aurora del workspace sin exponer un control en la UI: es
// lo primero que se sacrifica en equipos lentos (README §Fondo Plasma).
const WORKSPACE_AURORA_ENABLED = true

const AURORA_STOPS: Record<Theme, [string, string, string]> = {
  light: ["#B497CF", "#6200EE", "#B497CF"],
  dark: ["#03DAC6", "#5227FF", "#03DAC6"],
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

interface WorkspaceProps {
  onLogout: () => void
  theme: Theme
  onToggleTheme: () => void
}

function ActionButtons({
  onDiscard,
  onSave,
  saving,
}: {
  onDiscard: () => void
  onSave: () => void
  saving: boolean
}) {
  return (
    <div className="flex items-center gap-2.5">
      <button
        type="button"
        onClick={onDiscard}
        className="rounded-lg border px-3.5 py-2 text-[13px]"
        style={{ borderColor: "var(--border)", color: "var(--neg)" }}
      >
        Descartar
      </button>
      <button
        type="button"
        disabled={saving}
        onClick={onSave}
        className="rounded-lg px-4 py-2 text-[13px] font-semibold disabled:opacity-60"
        style={{ background: "var(--primary)", color: "var(--accent-fg)" }}
      >
        {saving ? "Guardando…" : "Guardar reporte"}
      </button>
    </div>
  )
}

function AnalyzeTab() {
  const [url, setUrl] = useState("")
  const [loading, setLoading] = useState(false)
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<ArticleAnalysis | null>(null)
  const [draft, setDraft] = useState<SaveArticlePayload | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!url.trim() || loading) return
    setLoading(true)
    setJobStatus(null)
    setError(null)
    setResult(null)
    setDraft(null)
    try {
      const data = await analyzeUrl(url.trim(), setJobStatus)
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
      setJobStatus(null)
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
      setError(err instanceof OdinApiError ? err.message : "No se pudo guardar el artículo.")
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
    setDraft((d) => (d ? { ...d, entities: d.entities.filter((_, i) => i !== index) } : d))
  }

  function discard() {
    setResult(null)
    setDraft(null)
  }

  const view = result
  const isDraft = draft !== null
  const cardValue: AnalysisCardFields | null = isDraft ? draft : view

  return (
    <div className="flex w-full flex-col gap-[22px]">
      <div
        className="rounded-xl border p-[22px]"
        style={{ background: "var(--panel)", borderColor: "var(--border)", boxShadow: "var(--shadow-sm)" }}
      >
        <div className="flex items-baseline gap-2">
          <h1 className="text-[19px] font-semibold">Analizar artículo</h1>
          <span className="font-mono text-[11px]" style={{ color: "var(--faint)" }}>
            POST /api/articles/analyze
          </span>
        </div>
        <p className="mt-1 mb-4 max-w-[70ch] text-[13px]" style={{ color: "var(--muted-foreground)" }}>
          Pegue la URL de la noticia. El sistema extrae el contenido y devuelve sentimiento,
          encuadre y actores para su revisión antes de guardar.
        </p>

        <form onSubmit={handleSubmit} className="flex flex-wrap gap-[9px]">
          <input
            type="url"
            required
            placeholder="https://www.diariolibre.com/…"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            className="h-11 min-w-[260px] flex-1 rounded-lg border px-[13px] font-mono text-[13px] outline-none focus-visible:ring-2"
            style={{ background: "var(--surface-2)", borderColor: "var(--border)" }}
          />
          <button
            type="submit"
            disabled={loading}
            className="rounded-lg px-5 py-[11px] text-[13.5px] font-semibold disabled:opacity-60"
            style={{ background: "var(--primary)", color: "var(--accent-fg)" }}
          >
            {loading ? "Analizando…" : "Analizar"}
          </button>
        </form>

        {error && (
          <div
            role="alert"
            className="mt-4 rounded-[7px] border px-3 py-2.5 text-[12.5px]"
            style={{ background: "var(--neg-soft)", borderColor: "var(--neg)", color: "var(--neg)" }}
          >
            <strong>No se pudo analizar</strong> {error}
          </div>
        )}

        {loading && (
          <div className="mt-[18px] border-t pt-[18px]" style={{ borderColor: "var(--border)" }}>
            <div className="mb-3 flex items-center gap-2.5 text-[12.5px]" style={{ color: "var(--muted-foreground)" }}>
              <span
                className="inline-block size-3 rounded-full"
                style={{
                  border: "2px solid var(--border-strong)",
                  borderTopColor: "var(--primary)",
                  animation: "odinSpin 0.8s linear infinite",
                }}
              />
              {jobStatus === "running"
                ? "Extrayendo y analizando con el modelo — puede tardar hasta un minuto."
                : "Encolando el análisis…"}
            </div>
            {[
              { h: 13, w: "55%", delay: "0s" },
              { h: 11, w: "100%", delay: "0.15s" },
              { h: 11, w: "88%", delay: "0.3s" },
              { h: 11, w: "40%", delay: "0.45s" },
            ].map((bar, i) => (
              <div
                key={i}
                className="mb-2 rounded"
                style={{
                  height: bar.h,
                  width: bar.w,
                  background: "var(--surface-3)",
                  animation: `odinPulse 1.6s ease-in-out ${bar.delay} infinite`,
                }}
              />
            ))}
          </div>
        )}
      </div>

      {view && cardValue && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            {view.already_saved ? (
              <span
                className="inline-flex items-center rounded-full border px-2.5 py-1 text-[11.5px] font-semibold"
                style={{ background: "var(--pos-soft)", color: "var(--pos)", borderColor: "var(--pos)" }}
              >
                Reporte guardado
              </span>
            ) : isDraft ? (
              <span
                className="inline-flex items-center rounded-full border px-2.5 py-1 text-[11.5px] font-semibold"
                style={{ background: "var(--accent-soft)", color: "var(--primary)", borderColor: "var(--accent-border)" }}
              >
                Vista previa · sin guardar
              </span>
            ) : (
              <span
                className="inline-flex items-center rounded-full border px-2.5 py-1 text-[11.5px] font-semibold"
                style={{ background: "var(--pos-soft)", color: "var(--pos)", borderColor: "var(--pos)" }}
              >
                Guardado en el archivo
              </span>
            )}
            {isDraft && <ActionButtons onDiscard={discard} onSave={handleSave} saving={saving} />}
          </div>

          <AnalysisCard
            value={cardValue}
            editable={isDraft}
            onChange={(patch) => setDraft((d) => (d ? { ...d, ...patch } : d))}
          />
          <EntitiesCard
            entities={isDraft ? draft.entities : view.entities}
            editable={isDraft}
            onUpdate={updateEntity}
            onRemove={removeEntity}
          />

          {isDraft && (
            <div className="flex justify-end">
              <ActionButtons onDiscard={discard} onSave={handleSave} saving={saving} />
            </div>
          )}
        </>
      )}
    </div>
  )
}

function Workspace({ onLogout, theme, onToggleTheme }: WorkspaceProps) {
  const [tab, setTab] = useState<"analyze" | "reports" | "entities" | "aliases" | "scrape">("analyze")

  return (
    <div className="relative min-h-screen" style={{ background: "var(--bg)" }}>
      {WORKSPACE_AURORA_ENABLED && (
        <div
          className="pointer-events-none absolute inset-x-0 top-0 z-0 h-[420px] overflow-hidden"
          style={{ opacity: theme === "dark" ? 0.5 : 0.35 }}
        >
          <Aurora colorStops={AURORA_STOPS[theme]} speed={0.4} blend={0.55} amplitude={0.9} />
          <div
            className="absolute inset-0"
            style={{ background: "linear-gradient(to bottom, transparent 0%, var(--bg) 88%)" }}
          />
        </div>
      )}

      <div className="relative z-[1] mx-auto max-w-[1180px] px-6 pt-[22px] pb-20">
        <Nav
          items={NAV_ITEMS}
          activeTab={tab}
          onTabChange={(t) => setTab(t as typeof tab)}
          username={getUsername()}
          onLogout={onLogout}
          theme={theme}
          onToggleTheme={onToggleTheme}
        />

        <main className="mt-[22px] flex flex-col gap-[22px]">
          {tab === "analyze" && <AnalyzeTab />}
          {tab === "reports" && <ReportsList />}
          {tab === "entities" && <CanonicalEntityManager />}
          {tab === "aliases" && <AliasManager />}
          {tab === "scrape" && <ScrapeTab />}
        </main>
      </div>
    </div>
  )
}

/**
 * Puerta de entrada: sin sesión válida no se monta nada del workspace.
 *
 * Al abrir la aplicación con un token guardado lo validamos contra
 * /api/auth/me — puede haber vencido o haber sido firmado con otro secreto
 * (la API reinició sin ODIN_JWT_SECRET). Mientras tanto se muestra una
 * pantalla en blanco (sin Aurora: evita montar/desmontar WebGL en una vista
 * transitoria) para no parpadear entre login y workspace.
 */
function App() {
  const [username, setUsername] = useState<string | null>(() =>
    getToken() ? getUsername() : null
  )
  const [checking, setChecking] = useState(() => Boolean(getToken()))
  const [theme, setTheme] = useState<Theme>(getInitialTheme)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try {
      localStorage.setItem(THEME_KEY, theme)
    } catch {
      // localStorage no disponible: el tema no persiste entre sesiones
    }
  }, [theme])

  function toggleTheme() {
    setTheme((t) => (t === "dark" ? "light" : "dark"))
  }

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

  return (
    <DialogProvider>
      {checking ? (
        <div className="min-h-screen" style={{ background: "var(--bg)" }} />
      ) : !username ? (
        <LoginScreen onSuccess={setUsername} theme={theme} />
      ) : (
        <Workspace onLogout={handleLogout} theme={theme} onToggleTheme={toggleTheme} />
      )}
    </DialogProvider>
  )
}

export default App
