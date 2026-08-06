import { useState } from "react"
import { AnimatePresence, motion } from "framer-motion"
import { BrainCircuit, Check, ChevronDown, ChevronRight, Loader2, Search, ShieldCheck } from "lucide-react"
import { cn } from "@/lib/utils"
import type { AnalyzeStage, JobStatus } from "@/lib/odin-api"

type StepState = "pending" | "active" | "done"

const STAGES: { key: AnalyzeStage; title: string; icon: typeof Search }[] = [
  { key: "fetching", title: "Descargando y extrayendo el artículo", icon: Search },
  { key: "analyzing", title: "Analizando con el modelo (sentimiento, encuadre, entidades)", icon: BrainCircuit },
  { key: "canonicalizing", title: "Canonicalizando entidades", icon: ShieldCheck },
]

function stepColor(state: StepState) {
  switch (state) {
    case "done":
      return { background: "var(--pos-soft)", color: "var(--pos)" }
    case "active":
      return { background: "var(--accent)", color: "var(--primary)" }
    case "pending":
      return { background: "var(--surface-2)", color: "var(--faint)" }
  }
}

/** Panel colapsable estilo "agent planning" para POST /api/analyze — timeline
 *  con conector vertical entre etapas, en vez de la lista simple anterior. */
export function AnalyzeProgress({
  jobStatus,
  stage,
}: {
  jobStatus: JobStatus | null
  stage: AnalyzeStage | null
}) {
  const [expanded, setExpanded] = useState(true)
  const currentIndex = stage ? STAGES.findIndex((s) => s.key === stage) : -1
  const allDone = currentIndex >= 0 && currentIndex === STAGES.length - 1 && jobStatus !== "running"

  return (
    <div
      className="mt-[18px] overflow-hidden rounded-xl border"
      style={{ borderColor: "var(--border)", background: "var(--card)" }}
    >
      <div
        onClick={() => setExpanded((v) => !v)}
        className={cn(
          "flex cursor-pointer select-none items-center justify-between px-4 py-3 transition-colors",
          expanded && "border-b",
        )}
        style={{ borderColor: "var(--border)" }}
      >
        <div className="flex items-center gap-2.5">
          {allDone ? (
            <Check className="size-4" style={{ color: "var(--pos)" }} />
          ) : (
            <Loader2 className="size-4 animate-spin" style={{ color: "var(--primary)" }} />
          )}
          <span className="text-[13.5px] font-semibold">
            {jobStatus === "running" ? "Analizando — puede tardar hasta un minuto" : "Encolando el análisis…"}
          </span>
        </div>
        <div className="text-muted-foreground">
          {expanded ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
        </div>
      </div>

      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: [0.2, 0.65, 0.3, 0.9] }}
            className="overflow-hidden"
          >
            <div className="flex flex-col p-4">
              {STAGES.map((s, i) => {
                const state: StepState = currentIndex < 0 ? "pending" : i < currentIndex ? "done" : i === currentIndex ? "active" : "pending"
                const isLast = i === STAGES.length - 1
                const StepIcon = s.icon
                return (
                  <div
                    key={s.key}
                    className={cn("relative flex gap-3", state === "pending" && "opacity-50")}
                  >
                    {!isLast && (
                      <div className="absolute left-[11px] top-7 bottom-[-4px] w-px" style={{ background: "var(--border)" }} />
                    )}
                    <div className="relative z-10 mt-0.5 flex-none">
                      <div
                        className="flex size-6 items-center justify-center rounded-full ring-4 transition-colors duration-300"
                        style={{ ...stepColor(state), ["--tw-ring-color" as string]: "var(--card)" }}
                      >
                        {state === "done" ? (
                          <Check className="size-3.5" />
                        ) : state === "active" ? (
                          <Loader2 className="size-3.5 animate-spin" />
                        ) : (
                          <StepIcon className="size-3.5" />
                        )}
                      </div>
                    </div>
                    <span
                      className={cn("pb-4 text-[13px]", state === "active" && "font-semibold")}
                      style={{ color: state === "pending" ? "var(--muted-foreground)" : "var(--foreground)" }}
                    >
                      {s.title}
                    </span>
                  </div>
                )
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
