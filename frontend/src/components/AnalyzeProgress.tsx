import { useEffect, useState } from "react"
import { ChevronDown } from "lucide-react"
import type { JobStatus, JobStep } from "@/lib/odin-api"

/** Pasos del pipeline agrupados en ramas, como un historial de git: el cliente
 *  fija la forma del grafo desde el primer segundo y el backend (`steps`) solo
 *  rellena estado, detalle y tiempos, por `key`. Las claves son las de
 *  `_StepLog` en services/analyze_service.py. */
const ANALYZE_PLAN = [
  {
    branch: "descarga",
    steps: [
      { key: "fetch", label: "Descargar la página" },
      { key: "extract", label: "Extraer el artículo" },
    ],
  },
  {
    branch: "análisis",
    steps: [
      { key: "analyze", label: "Analizar con el modelo" },
      { key: "places", label: "Detectar lugares" },
    ],
  },
  {
    branch: "consolidación",
    steps: [
      { key: "canonicalize", label: "Canonicalizar entidades" },
      { key: "classify", label: "Sugerir temas y localidades" },
    ],
  },
] as const

type NodeState = "pending" | "active" | "done" | "skipped" | "failed"

interface Row {
  key: string
  label: string
  state: NodeState
  detail: string | null
  startedMs: number | null
  durationMs: number | null
  first: boolean
}

interface Branch {
  name: string
  rows: Row[]
  state: "pending" | "active" | "done"
}

/** Une el plan estático con lo que reportó el backend. Un paso que no llegó a
 *  empezar pero tiene posteriores ya iniciados (p. ej. `places` cuando el motor
 *  ya devolvió los lugares) se muestra como omitido. */
function buildBranches(steps: JobStep[]): Branch[] {
  const byKey = new Map(steps.map((s) => [s.key, s]))
  const flat = ANALYZE_PLAN.flatMap((b) => b.steps.map((s) => s.key as string))
  const lastStarted = Math.max(-1, ...steps.map((s) => flat.indexOf(s.key)))
  // Antes del primer reporte del backend, el primer paso ya es el que viene.
  const nothingYet = steps.length === 0

  return ANALYZE_PLAN.map((b) => {
    const rows: Row[] = b.steps.map((p, i) => {
      const s = byKey.get(p.key)
      const idx = flat.indexOf(p.key)
      let state: NodeState = "pending"
      if (s) state = s.status === "running" ? "active" : s.status === "failed" ? "failed" : "done"
      else if (idx < lastStarted) state = "skipped"
      else if (nothingYet && idx === 0) state = "active"
      return {
        key: p.key,
        label: p.label,
        state,
        detail: s?.detail ?? (state === "skipped" ? "no hizo falta" : null),
        startedMs: s?.started_ms ?? null,
        durationMs: s?.duration_ms ?? null,
        first: i === 0,
      }
    })
    const settled = rows.every((r) => r.state === "done" || r.state === "skipped")
    const touched = rows.some((r) => r.state !== "pending")
    return { name: b.branch, rows, state: settled ? "done" : touched ? "active" : "pending" }
  })
}

function formatSeconds(ms: number): string {
  return `${(Math.max(0, ms) / 1000).toFixed(1)} s`
}

function useNow(active: boolean): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!active) return
    const id = setInterval(() => setNow(Date.now()), 200)
    return () => clearInterval(id)
  }, [active])
  return now
}

const ROW_H = "h-8"
const CURVE_H = 14

/** Curva que sale del riel principal hacia la rama (`fork`) o vuelve (`merge`). */
function Connector({ kind, state }: { kind: "fork" | "merge"; state: Branch["state"] }) {
  const d = kind === "fork" ? "M7.5 0 C7.5 9 19.5 5 19.5 14" : "M19.5 0 C19.5 9 7.5 5 7.5 14"
  return (
    <svg
      aria-hidden
      width="28"
      height={CURVE_H}
      viewBox={`0 0 28 ${CURVE_H}`}
      fill="none"
      className={state === "pending" ? "text-border" : "text-primary"}
    >
      <path d={d} stroke="currentColor" strokeWidth="1.5" />
    </svg>
  )
}

function Node({ state }: { state: NodeState }) {
  const base = "absolute top-1/2 left-[20px] size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full"
  if (state === "active") {
    return (
      <>
        <span aria-hidden className={`${base} odin-ring bg-primary`} />
        <span aria-hidden className={`${base} border-2 border-primary bg-card`} />
      </>
    )
  }
  if (state === "done") return <span aria-hidden className={`${base} bg-primary`} />
  if (state === "failed") return <span aria-hidden className={`${base} bg-destructive`} />
  if (state === "skipped") return <span aria-hidden className={`${base} border border-dashed border-border bg-card`} />
  return <span aria-hidden className={`${base} border border-border bg-card`} />
}

/** Timeline de progreso real del análisis, con la forma de un historial de git. */
export function AnalyzeProgress({
  jobStatus,
  steps,
  startedAt,
}: {
  jobStatus: JobStatus | null
  steps: JobStep[]
  startedAt: number
}) {
  const [open, setOpen] = useState(true)
  const now = useNow(true)
  const elapsed = now - startedAt
  const branches = buildBranches(steps)
  const rows = branches.flatMap((b) => b.rows)
  const doneCount = rows.filter((r) => r.state === "done" || r.state === "skipped").length
  const activeRow = rows.find((r) => r.state === "active")
  const queued = steps.length === 0 && jobStatus !== "running"
  const heading = queued ? "Encolando el análisis" : (activeRow?.label ?? "Analizando")

  let rowIndex = 0
  return (
    <div className="mt-4 rounded-xl border bg-card p-3 odin-pop" style={{ transformOrigin: "top left" }}>
      {/* Región viva sin contadores: solo anuncia el paso en curso. */}
      <p role="status" aria-live="polite" className="sr-only">
        {heading}
      </p>
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 rounded-md text-left text-sm text-muted-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <ChevronDown
          aria-hidden
          className="size-4 shrink-0"
          style={{ transform: open ? "none" : "rotate(-90deg)", transition: "transform 160ms var(--ease-out)" }}
        />
        <span aria-hidden className="font-medium text-foreground">
          {heading}
        </span>
        <span aria-hidden className="font-mono text-xs text-[var(--faint)]">
          · {Math.floor(elapsed / 1000)} s
        </span>
      </button>

      {open && (
        <ol aria-hidden className="relative mt-2 list-none p-0">
          {/* Riel principal: fondo y relleno que crece con los pasos completados. */}
          <span className="absolute top-0 bottom-0 left-[7px] w-px bg-border" />
          <span
            className="absolute top-0 bottom-0 left-[7px] w-px origin-top bg-primary"
            style={{
              transform: `scaleY(${doneCount / rows.length})`,
              transition: "transform 280ms var(--ease-out)",
            }}
          />
          {branches.map((b) => (
            <li key={b.name} className="relative">
              <Connector kind="fork" state={b.state} />
              <div className="relative">
                <span
                  className={`absolute top-0 bottom-0 left-[19px] w-px ${b.state === "pending" ? "bg-border" : "bg-primary"}`}
                />
                <ul className="list-none p-0">
                  {b.rows.map((r) => {
                    const delay = rowIndex++ * 40
                    return (
                      <li
                        key={r.key}
                        className={`odin-enter relative flex ${ROW_H} items-center gap-2 text-sm`}
                        style={{ animationDelay: `${delay}ms` }}
                      >
                        <span className="relative h-full w-7 shrink-0">
                          <Node state={r.state} />
                        </span>
                        <span className={r.state === "pending" || r.state === "skipped" ? "text-muted-foreground" : "text-foreground"}>
                          {r.label}
                        </span>
                        {r.first && (
                          <span className="rounded bg-[var(--accent-soft)] px-1.5 py-0.5 font-mono text-[11px] text-primary">
                            {b.name}
                          </span>
                        )}
                        <span className="ml-auto flex items-baseline gap-2 font-mono text-xs text-[var(--faint)]">
                          {r.detail && <span className="truncate">{r.detail}</span>}
                          {r.state === "active" && (
                            <span className="tabular-nums">{formatSeconds(elapsed - (r.startedMs ?? 0))}</span>
                          )}
                          {(r.state === "done" || r.state === "failed") && r.durationMs !== null && (
                            <span className="tabular-nums">{formatSeconds(r.durationMs)}</span>
                          )}
                        </span>
                      </li>
                    )
                  })}
                </ul>
              </div>
              <Connector kind="merge" state={b.state} />
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
