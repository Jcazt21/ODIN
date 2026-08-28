import { useState, type FormEvent } from "react"
import { AnalysisCard, type AnalysisCardFields } from "@/components/AnalysisCard"
import { LocalityPicker } from "@/components/LocalityPicker"
import type { PickedLocality } from "@/lib/localities"
import { AnalyzeProgress } from "@/components/AnalyzeProgress"
import { EntitiesCard } from "@/components/EntitiesCard"
import { ActionButtons } from "@/components/ActionButtons"
import { useAnalyzeUrl, useSaveArticle } from "@/lib/queries/articles"
import type { EntityFields } from "@/components/EntitiesCard"
import {
  OdinApiError,
  type AnalyzeResult,
  type AnalyzeStage,
  type ArticleAnalysis,
  type JobStatus,
  type SaveArticlePayload,
} from "@/lib/odin-api"

function toDraft(a: AnalyzeResult): SaveArticlePayload {
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

function errorMessage(err: unknown, fallback: string): string {
  return err instanceof OdinApiError
    ? err.message
    : fallback
}

export function AnalyzePage() {
  const [url, setUrl] = useState("")
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null)
  const [jobStage, setJobStage] = useState<AnalyzeStage | null>(null)
  const [result, setResult] = useState<AnalyzeResult | ArticleAnalysis | null>(null)
  const [draft, setDraft] = useState<SaveArticlePayload | null>(null)

  const analyzeMutation = useAnalyzeUrl((status, stage) => {
    setJobStatus(status)
    setJobStage(stage)
  })
  const saveMutation = useSaveArticle()
  // Los lugares se acumulan acá y viajan en el mismo POST que el reporte.
  // No se escriben al vuelo como en `LocalitiesCard` porque todavía no hay
  // artículo al que vincularlos: existe recién al guardar, y por eso el
  // guardado es una sola transacción que los incluye.
  const [localities, setLocalities] = useState<PickedLocality[]>([])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!url.trim() || analyzeMutation.isPending) return
    setJobStatus(null)
    setJobStage(null)
    setResult(null)
    setDraft(null)
    try {
      const data = await analyzeMutation.mutateAsync(url.trim())
      setResult(data)
      if (!data.already_saved) setDraft(toDraft(data))
    } catch {
      // el error queda en analyzeMutation.error, mostrado abajo
    } finally {
      setJobStatus(null)
      setJobStage(null)
    }
  }

  async function handleSave() {
    if (!draft || saveMutation.isPending) return
    try {
      const saved = await saveMutation.mutateAsync({
        ...draft,
        localities: localities.map((l) => ({
          locality_id: l.locality_id,
          kind: l.kind,
          origin: "MANUAL",
          confidence: null,
        })),
      })
      setResult(saved)
      setDraft(null)
      setLocalities([])
      setUrl("")
    } catch {
      // el error queda en saveMutation.error, mostrado abajo
    }
  }

  function updateEntity(index: number, patch: Partial<EntityFields>) {
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
    analyzeMutation.reset()
    saveMutation.reset()
  }

  const loading = analyzeMutation.isPending
  const saving = saveMutation.isPending
  const error = analyzeMutation.error
    ? errorMessage(analyzeMutation.error, "No se pudo conectar con la API de Odin. ¿Está corriendo en el puerto 8000?")
    : saveMutation.error
      ? errorMessage(saveMutation.error, "No se pudo guardar el artículo.")
      : null

  const view = result
  const isDraft = draft !== null
  const cardValue: AnalysisCardFields | null = isDraft ? draft : view

  return (
    <div className="flex w-full flex-col gap-[22px]">
      <div
        className="odin-glass rounded-xl border p-[22px]"
        style={{ boxShadow: "var(--shadow-sm)" }}
      >
        <div className="flex items-baseline gap-2">
          <h1 className="text-[19px] font-semibold">Analizar artículo</h1>
          <span className="font-mono text-[11px]" style={{ color: "var(--faint)" }}>
            POST /api/analyze
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

        {loading && <AnalyzeProgress jobStatus={jobStatus} stage={jobStage} />}
      </div>

      {view && cardValue && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            {"already_saved" in view && view.already_saved ? (
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
          {isDraft && (
            <div
              className="odin-glass overflow-hidden rounded-xl border px-6 py-5"
              style={{ boxShadow: "var(--shadow-sm)" }}
            >
              <h3 className="text-[15px] font-semibold">Lugar de la noticia</h3>
              <p className="mt-1 mb-3 text-[12.5px]" style={{ color: "var(--muted-foreground)" }}>
                Se guardan junto con el reporte. Podés agregar más de uno.
              </p>
              <LocalityPicker
                selected={localities}
                onAdd={(picked) => setLocalities((prev) => [...prev, picked])}
                onRemove={(_picked, index) =>
                  setLocalities((prev) => prev.filter((_, i) => i !== index))
                }
              />
            </div>
          )}
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
