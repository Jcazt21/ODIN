import { PageHeader } from "@/components/PageHeader"
import { useRef, useState, type FormEvent } from "react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { AnalysisCard, type AnalysisCardFields } from "@/components/AnalysisCard"
import { LocalityPicker } from "@/components/LocalityPicker"
import { suggestedToPicked, type PickedLocality } from "@/lib/localities"
import { AnalyzeProgress } from "@/components/AnalyzeProgress"
import { ArticleBody } from "@/components/ArticleBody"
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

function isHttpUrl(value: string): boolean {
  try {
    const { protocol } = new URL(value)
    return protocol === "http:" || protocol === "https:"
  } catch {
    return false
  }
}

export function AnalyzePage() {
  const [url, setUrl] = useState("")
  const [urlError, setUrlError] = useState<string | null>(null)
  const urlInputRef = useRef<HTMLInputElement>(null)
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

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    void runAnalysis()
  }

  async function runAnalysis() {
    if (analyzeMutation.isPending) return
    if (!isHttpUrl(url.trim())) {
      setUrlError("Escribe un enlace válido, por ejemplo https://www.diariolibre.com/…")
      return
    }
    setUrlError(null)
    setJobStatus(null)
    setJobStage(null)
    setResult(null)
    setDraft(null)
    try {
      const data = await analyzeMutation.mutateAsync(url.trim())
      setResult(data)
      if (!data.already_saved) {
        setDraft(toDraft(data))
        // Precarga: el documentalista confirma o quita, no arranca de cero.
        setLocalities(suggestedToPicked(data.suggested_localities ?? []))
      }
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
          // Lo que agrega una persona en el selector llega sin `origin` y cae
          // en MANUAL; lo que sobrevive de las sugerencias conserva AUTO.
          origin: l.origin ?? "MANUAL",
          confidence: l.origin === "AUTO" ? (l.confidence ?? null) : null,
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

  function analyzeAnother() {
    discard()
    setUrl("")
    urlInputRef.current?.focus()
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
    ? errorMessage(analyzeMutation.error, "No se pudo conectar con la API de Odin. ¿Está corriendo en el puerto 8001?")
    : saveMutation.error
      ? errorMessage(saveMutation.error, "No se pudo guardar el artículo.")
      : null

  const view = result
  const isDraft = draft !== null
  const cardValue: AnalysisCardFields | null = isDraft ? draft : view

  return (
    <div className="flex w-full flex-col gap-6">
      <section>
        <div className="mb-5">
          <PageHeader
            title="Analizar artículo"
            subtitle="Pega el enlace de la noticia. Revisarás el sentimiento, el encuadre y los actores antes de guardar."
          />
        </div>

        <form onSubmit={handleSubmit} noValidate className="flex flex-wrap gap-2">
          <input
            ref={urlInputRef}
            autoFocus
            type="text"
            inputMode="url"
            aria-label="Enlace de la noticia"
            aria-invalid={urlError ? true : undefined}
            aria-describedby={urlError ? "analyze-url-error" : undefined}
            placeholder="https://www.diariolibre.com/…"
            value={url}
            disabled={loading}
            onChange={(e) => setUrl(e.target.value)}
            className="h-12 min-w-[260px] flex-1 rounded-xl border bg-[var(--surface)] px-3.5 font-mono text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
          <Button type="submit" size="lg" className="h-12 rounded-xl px-6 text-sm" disabled={loading}>
            {loading ? "Analizando…" : "Analizar"}
          </Button>
        </form>
        {urlError && (
          <p id="analyze-url-error" className="mt-2 text-sm text-destructive">
            {urlError}
          </p>
        )}

        {error && (
          <Alert variant="destructive" className="mt-4 items-center sm:grid-cols-[1fr_auto]">
            <AlertDescription>
              <strong>No se pudo analizar.</strong> {error}
            </AlertDescription>
            {analyzeMutation.error && (
              <Button type="button" variant="outline" size="sm" onClick={() => runAnalysis()}>
                Reintentar
              </Button>
            )}
          </Alert>
        )}

        {loading && <AnalyzeProgress jobStatus={jobStatus} stage={jobStage} />}
      </section>

      {view && cardValue && (
        <>
          <div className="odin-enter">
            <AnalysisCard
              value={cardValue}
              editable={isDraft}
              onChange={(patch) => setDraft((d) => (d ? { ...d, ...patch } : d))}
            />
          </div>
          {isDraft && (
            // Sin overflow-hidden: recortaría el desplegable del selector de
            // lugares, que se posiciona absoluto y se sale de la sección.
            <section className="border-t pt-6">
              <h3 className="text-base font-semibold">Lugar de la noticia</h3>
              <p className="mt-1 mb-3 text-sm text-muted-foreground">
                Se guardan junto con el reporte. Puedes agregar más de uno.
              </p>
              <LocalityPicker
                selected={localities}
                onAdd={(picked) => setLocalities((prev) => [...prev, picked])}
                onRemove={(_picked, index) =>
                  setLocalities((prev) => prev.filter((_, i) => i !== index))
                }
              />
            </section>
          )}
          <EntitiesCard
            entities={isDraft ? draft.entities : view.entities}
            editable={isDraft}
            onUpdate={updateEntity}
            onRemove={removeEntity}
          />
          <ArticleBody body={cardValue.body} />

          <ActionButtons
            state={isDraft ? "draft" : "saved"}
            reportId={"id" in view && typeof view.id === "number" ? view.id : undefined}
            saving={saving}
            onSave={handleSave}
            onDiscard={discard}
            onAnalyzeAnother={analyzeAnother}
          />
        </>
      )}
    </div>
  )
}
