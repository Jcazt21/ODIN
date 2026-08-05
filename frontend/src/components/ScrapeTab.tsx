import { useEffect, useRef, useState, type FormEvent } from "react"
import { AnimatePresence, motion } from "framer-motion"
import { CheckCircle2, Circle, CircleAlert, CircleDotDashed, CircleX } from "lucide-react"
import {
  cancelScrapeJob,
  listScrapeJobs,
  pollScrapeJob,
  startScrapeJob,
  OdinApiError,
  type ScrapeJob,
  type ScrapeSourceProgress,
} from "@/lib/odin-api"

// Las 9 fuentes del scraper de política (scrapers/SCRAPERS en el backend) —
// fijas a propósito, no vienen de un endpoint: esta tab solo corre ESE
// scraper (no un panel general de crawl), así que la lista cambia con la
// misma frecuencia que el propio backend. Si se agrega/quita una fuente ahí,
// hay que reflejarlo acá también.
const SOURCES: { key: string; label: string }[] = [
  { key: "listin_diario", label: "Listín Diario" },
  { key: "diario_libre", label: "Diario Libre" },
  { key: "el_nacional", label: "El Nacional" },
  { key: "hoy", label: "Hoy" },
  { key: "el_caribe", label: "El Caribe" },
  { key: "al_momento", label: "Al Momento" },
  { key: "el_dia", label: "El Día" },
  { key: "n_digital", label: "N Digital" },
  { key: "acento", label: "Acento" },
]

const STAGE_LABELS: Record<string, string> = {
  discover: "Descubrimiento y filtrado",
  analyze: "Análisis y guardado",
}

type Status = "pending" | "running" | "done" | "failed" | "cancelled"

function StatusIcon({ status }: { status: Status }) {
  const common = "size-4"
  return (
    <AnimatePresence mode="wait">
      <motion.span
        key={status}
        initial={{ opacity: 0, scale: 0.8, rotate: -10 }}
        animate={{ opacity: 1, scale: 1, rotate: 0 }}
        exit={{ opacity: 0, scale: 0.8, rotate: 10 }}
        transition={{ duration: 0.2, ease: [0.2, 0.65, 0.3, 0.9] }}
        className="inline-flex"
      >
        {status === "done" && <CheckCircle2 className={common} style={{ color: "var(--pos)" }} />}
        {status === "running" && (
          <motion.span
            animate={{ rotate: 360 }}
            transition={{ duration: 1.1, ease: "linear", repeat: Infinity }}
            className="inline-flex"
          >
            <CircleDotDashed className={common} style={{ color: "var(--primary)" }} />
          </motion.span>
        )}
        {status === "failed" && <CircleX className={common} style={{ color: "var(--neg)" }} />}
        {status === "cancelled" && <CircleAlert className={common} style={{ color: "var(--warn)" }} />}
        {status === "pending" && <Circle className={common} style={{ color: "var(--faint)" }} />}
      </motion.span>
    </AnimatePresence>
  )
}

/** Estado combinado de una fuente a partir de sus 2 subtareas (discover,
 *  analyze), para el ícono de la fila padre: "running" si cualquiera está
 *  corriendo, si no el de la última etapa alcanzada. */
function sourceStatus(discover?: ScrapeSourceProgress, analyze?: ScrapeSourceProgress): Status {
  if (analyze) return analyze.status as Status
  if (discover) return discover.status as Status
  return "pending"
}

function SourceRow({
  label,
  discover,
  analyze,
}: {
  label: string
  discover?: ScrapeSourceProgress
  analyze?: ScrapeSourceProgress
}) {
  const subtasks = [
    { stage: "discover", data: discover },
    { stage: "analyze", data: analyze },
  ]

  return (
    <motion.li
      layout
      initial={{ opacity: 0, y: -5 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", stiffness: 500, damping: 30 }}
      className="py-1.5"
    >
      <div className="flex items-center gap-2.5 px-1">
        <StatusIcon status={sourceStatus(discover, analyze)} />
        <span className="text-[13.5px] font-medium">{label}</span>
      </div>
      <ul className="mt-1 ml-[26px] space-y-1 border-l pl-3" style={{ borderColor: "var(--border)" }}>
        {subtasks.map(({ stage, data }) => (
          <li key={stage} className="flex items-start gap-2">
            <span className="mt-[1px]">
              <StatusIcon status={(data?.status as Status) ?? "pending"} />
            </span>
            <span className="text-[12px]" style={{ color: "var(--muted-foreground)" }}>
              {STAGE_LABELS[stage]}
              {data?.detail && (
                <span className="block text-[11.5px]" style={{ color: "var(--faint)" }}>
                  {data.detail}
                </span>
              )}
            </span>
          </li>
        ))}
      </ul>
    </motion.li>
  )
}

const JOB_STATUS_LABELS: Record<string, string> = {
  pending: "En cola…",
  running: "Corriendo…",
  done: "Completado",
  failed: "Falló",
  cancelled: "Cancelado",
}

function JobPanel({ job, onCancel, onReset, cancelling }: {
  job: ScrapeJob
  onCancel: () => void
  onReset: () => void
  cancelling: boolean
}) {
  const bySource = new Map<string, { discover?: ScrapeSourceProgress; analyze?: ScrapeSourceProgress }>()
  for (const entry of Object.values(job.progress)) {
    const cur = bySource.get(entry.source) ?? {}
    if (entry.stage === "discover") cur.discover = entry
    if (entry.stage === "analyze") cur.analyze = entry
    bySource.set(entry.source, cur)
  }

  const active = job.status === "pending" || job.status === "running"
  const cr = job.crawl_run

  return (
    <div
      className="rounded-xl border p-[22px]"
      style={{ background: "var(--panel)", borderColor: "var(--border)", boxShadow: "var(--shadow-sm)" }}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <StatusIcon status={job.status as Status} />
          <h2 className="text-[15.5px] font-semibold">{JOB_STATUS_LABELS[job.status] ?? job.status}</h2>
          <span className="font-mono text-[11px]" style={{ color: "var(--faint)" }}>
            objetivo {job.target} · tope {job.per_source_cap}/fuente · {job.analyzer}
          </span>
        </div>
        {active ? (
          <button
            type="button"
            onClick={onCancel}
            disabled={cancelling || job.status === "pending"}
            className="rounded-lg border px-3.5 py-2 text-[13px] disabled:opacity-60"
            style={{ borderColor: "var(--border)", color: "var(--neg)" }}
          >
            {cancelling ? "Cancelando…" : "Cancelar"}
          </button>
        ) : (
          <button
            type="button"
            onClick={onReset}
            className="rounded-lg px-4 py-2 text-[13px] font-semibold"
            style={{ background: "var(--primary)", color: "var(--accent-fg)" }}
          >
            Nueva corrida
          </button>
        )}
      </div>

      <ul className="mt-4">
        {SOURCES.map(({ key, label }) => (
          <SourceRow key={key} label={label} discover={bySource.get(key)?.discover} analyze={bySource.get(key)?.analyze} />
        ))}
      </ul>

      {cr && (
        <div className="mt-4 flex flex-wrap gap-4 border-t pt-4 text-[12.5px]" style={{ borderColor: "var(--border)", color: "var(--muted-foreground)" }}>
          <span>Descubiertos: <strong>{cr.articles_discovered}</strong></span>
          <span>Guardados: <strong style={{ color: "var(--pos)" }}>{cr.articles_saved}</strong></span>
          <span>Fallidos: <strong style={{ color: cr.articles_failed ? "var(--neg)" : undefined }}>{cr.articles_failed}</strong></span>
        </div>
      )}
      {job.error && (
        <div
          role="alert"
          className="mt-4 rounded-[7px] border px-3 py-2.5 text-[12.5px]"
          style={{ background: "var(--neg-soft)", borderColor: "var(--neg)", color: "var(--neg)" }}
        >
          {job.error}
        </div>
      )}
      {active && (
        <p className="mt-3 text-[11.5px]" style={{ color: "var(--faint)" }}>
          Cancelar es cooperativo: puede tardar hasta que termine de descargar la fuente actual.
        </p>
      )}
    </div>
  )
}

export function ScrapeTab() {
  const [job, setJob] = useState<ScrapeJob | null>(null)
  const [checkingActive, setCheckingActive] = useState(true)
  const [starting, setStarting] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [target, setTarget] = useState(250)
  const [perSourceCap, setPerSourceCap] = useState<number | "">("")
  const [analyzer, setAnalyzer] = useState<"local" | "groq" | "hybrid">("local")

  const stopPollRef = useRef<(() => void) | null>(null)

  function beginPolling(jobId: string) {
    stopPollRef.current?.()
    stopPollRef.current = pollScrapeJob(jobId, setJob)
  }

  // Al montar: si ya hay una corrida pending/running (p. ej. tras recargar la
  // página), retoma el polling en vez de mostrar el formulario de nuevo.
  useEffect(() => {
    let alive = true
    listScrapeJobs(1)
      .then((jobs) => {
        if (!alive) return
        const latest = jobs[0]
        if (latest && (latest.status === "pending" || latest.status === "running")) {
          setJob(latest)
          beginPolling(latest.job_id)
        }
      })
      .catch(() => {
        // sin corridas previas o error de red al consultar: se cae al formulario
      })
      .finally(() => alive && setCheckingActive(false))
    return () => {
      alive = false
      stopPollRef.current?.()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function handleStart(e: FormEvent) {
    e.preventDefault()
    if (starting) return
    setStarting(true)
    setError(null)
    try {
      const accepted = await startScrapeJob({
        target,
        per_source_cap: perSourceCap === "" ? undefined : perSourceCap,
        analyzer,
      })
      setJob({
        job_id: accepted.job_id,
        status: "pending",
        target,
        per_source_cap: perSourceCap === "" ? Math.ceil(target / SOURCES.length) : perSourceCap,
        analyzer,
        created_at: new Date().toISOString(),
        started_at: null,
        finished_at: null,
        progress: {},
        crawl_run: null,
        error: null,
      })
      beginPolling(accepted.job_id)
    } catch (err) {
      setError(err instanceof OdinApiError ? err.message : "No se pudo iniciar la corrida.")
    } finally {
      setStarting(false)
    }
  }

  async function handleCancel() {
    if (!job || cancelling) return
    setCancelling(true)
    try {
      const updated = await cancelScrapeJob(job.job_id)
      setJob(updated)
    } catch (err) {
      setError(err instanceof OdinApiError ? err.message : "No se pudo cancelar la corrida.")
    } finally {
      setCancelling(false)
    }
  }

  function handleReset() {
    stopPollRef.current?.()
    setJob(null)
  }

  if (checkingActive) {
    return <div className="h-40" />
  }

  return (
    <div className="flex w-full flex-col gap-[22px]">
      {!job && (
        <div
          className="rounded-xl border p-[22px]"
          style={{ background: "var(--panel)", borderColor: "var(--border)", boxShadow: "var(--shadow-sm)" }}
        >
          <div className="flex items-baseline gap-2">
            <h1 className="text-[19px] font-semibold">Scraper de política</h1>
            <span className="font-mono text-[11px]" style={{ color: "var(--faint)" }}>
              POST /api/scrape-jobs
            </span>
          </div>
          <p className="mt-1 mb-4 max-w-[70ch] text-[13px]" style={{ color: "var(--muted-foreground)" }}>
            Rastrea las 9 fuentes permitidas filtrando solo noticias de política dominicana, para
            construir la base del golden set (task.md §2.4).
          </p>

          <form onSubmit={handleStart} className="flex flex-wrap items-end gap-[14px]">
            <label className="flex flex-col gap-1">
              <span className="text-[11.5px] font-medium" style={{ color: "var(--muted-foreground)" }}>
                Objetivo
              </span>
              <input
                type="number"
                min={1}
                max={2000}
                value={target}
                onChange={(e) => setTarget(Number(e.target.value))}
                className="h-10 w-[110px] rounded-lg border px-3 font-mono text-[13px] outline-none focus-visible:ring-2"
                style={{ background: "var(--surface-2)", borderColor: "var(--border)" }}
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-[11.5px] font-medium" style={{ color: "var(--muted-foreground)" }}>
                Tope por fuente
              </span>
              <input
                type="number"
                min={1}
                placeholder="auto"
                value={perSourceCap}
                onChange={(e) => setPerSourceCap(e.target.value === "" ? "" : Number(e.target.value))}
                className="h-10 w-[110px] rounded-lg border px-3 font-mono text-[13px] outline-none focus-visible:ring-2"
                style={{ background: "var(--surface-2)", borderColor: "var(--border)" }}
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-[11.5px] font-medium" style={{ color: "var(--muted-foreground)" }}>
                Analizador
              </span>
              <select
                value={analyzer}
                onChange={(e) => setAnalyzer(e.target.value as typeof analyzer)}
                className="h-10 rounded-lg border px-3 text-[13px] outline-none focus-visible:ring-2"
                style={{ background: "var(--surface-2)", borderColor: "var(--border)" }}
              >
                <option value="local">local (gratis)</option>
                <option value="groq">groq</option>
                <option value="hybrid">hybrid</option>
              </select>
            </label>
            <button
              type="submit"
              disabled={starting}
              className="h-10 rounded-lg px-5 text-[13.5px] font-semibold disabled:opacity-60"
              style={{ background: "var(--primary)", color: "var(--accent-fg)" }}
            >
              {starting ? "Iniciando…" : "Iniciar corrida"}
            </button>
          </form>

          {error && (
            <div
              role="alert"
              className="mt-4 rounded-[7px] border px-3 py-2.5 text-[12.5px]"
              style={{ background: "var(--neg-soft)", borderColor: "var(--neg)", color: "var(--neg)" }}
            >
              {error}
            </div>
          )}
        </div>
      )}

      {job && (
        <JobPanel job={job} onCancel={handleCancel} onReset={handleReset} cancelling={cancelling} />
      )}
    </div>
  )
}
