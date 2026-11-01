import { Loader2 } from "lucide-react"
import type { AnalyzeStage, JobStatus } from "@/lib/odin-api"

const STAGE_LABELS: Record<AnalyzeStage, string> = {
  fetching: "Descargando y extrayendo el artículo…",
  analyzing: "Analizando con el modelo (sentimiento, encuadre, entidades)…",
  canonicalizing: "Canonicalizando entidades…",
}

function label(jobStatus: JobStatus | null, stage: AnalyzeStage | null): string {
  if (stage) return STAGE_LABELS[stage]
  return jobStatus === "running" ? "Analizando — puede tardar hasta un minuto" : "Encolando el análisis…"
}

/** Una línea bajo el campo con la etapa actual; `role="status"` la anuncia a lectores de pantalla. */
export function AnalyzeProgress({
  jobStatus,
  stage,
}: {
  jobStatus: JobStatus | null
  stage: AnalyzeStage | null
}) {
  return (
    <p role="status" className="mt-3 flex items-center gap-2 text-sm text-muted-foreground">
      <Loader2 aria-hidden className="size-4 animate-spin text-primary" />
      {label(jobStatus, stage)}
    </p>
  )
}
