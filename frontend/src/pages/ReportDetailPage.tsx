import { useState } from "react"
import { PageHeader } from "@/components/PageHeader"
import { Link, useNavigate, useParams } from "react-router-dom"
import { ChevronLeft, Pencil, Trash2 } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { AnalysisCard, type AnalysisCardFields } from "@/components/AnalysisCard"
import { ArticleBody } from "@/components/ArticleBody"
import { EntitiesCard } from "@/components/EntitiesCard"
import { LocalitiesCard } from "@/components/LocalitiesCard"
import { useConfirm } from "@/lib/dialog"
import { useArticle, useUpdateArticle, useDeleteArticle } from "@/lib/queries/articles"
import { OdinApiError, type ArticleAnalysis, type ArticleUpdatePayload } from "@/lib/odin-api"

type EditableFields = Pick<
  AnalysisCardFields,
  | "authors"
  | "main_topic"
  | "topic_keywords"
  | "overall_sentiment"
  | "sentiment_score"
  | "framing"
  | "headline_intent"
  | "lead_orientation"
  | "source_quality"
  | "has_hard_data"
  | "dominant_actor"
  | "blamed_actor"
  | "credited_actor"
>

function toEditForm(article: ArticleAnalysis): EditableFields {
  return {
    authors: article.authors,
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

export function ReportDetailPage() {
  const params = useParams<{ id: string }>()
  const id = Number(params.id)
  const navigate = useNavigate()
  const confirm = useConfirm()

  const { data: article, isLoading, error } = useArticle(Number.isFinite(id) ? id : null)
  const updateMutation = useUpdateArticle()
  const deleteMutation = useDeleteArticle()

  const [editing, setEditing] = useState(false)
  const [editForm, setEditForm] = useState<EditableFields | null>(null)

  function onBack() {
    navigate("/reports")
  }

  function startEditing() {
    if (!article) return
    setEditForm(toEditForm(article))
    updateMutation.reset()
    setEditing(true)
  }

  async function handleSaveEdit() {
    if (!article || !editForm) return
    try {
      await updateMutation.mutateAsync({ id: article.id as number, payload: editForm as ArticleUpdatePayload })
      setEditing(false)
    } catch {
      // el error queda en updateMutation.error
    }
  }

  async function handleDelete() {
    if (!article) return
    const ok = await confirm({
      title: "¿Eliminar este reporte?",
      body: `Se eliminará permanentemente "${article.title}". Esta acción no se puede deshacer.`,
      confirmLabel: "Eliminar",
      danger: true,
    })
    if (!ok) return
    try {
      await deleteMutation.mutateAsync(article.id as number)
      onBack()
    } catch {
      // el error queda en deleteMutation.error
    }
  }

  const cardValue: AnalysisCardFields | null = article
    ? editing && editForm
      ? { ...article, ...editForm }
      : article
    : null

  const saving = updateMutation.isPending
  const deleting = deleteMutation.isPending
  const saveError = updateMutation.error instanceof OdinApiError ? updateMutation.error.message : updateMutation.error ? "Error guardando la rectificación." : null
  const deleteError = deleteMutation.error instanceof OdinApiError ? deleteMutation.error.message : deleteMutation.error ? "Error eliminando el reporte." : null
  const loadError = error instanceof OdinApiError ? error.message : error ? "No se pudo cargar el reporte." : null

  return (
    <div className="flex w-full flex-col gap-6">
      <PageHeader title="Detalle del reporte" />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link
          to="/reports"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors duration-150 hover:text-foreground"
        >
          <ChevronLeft aria-hidden className="size-4" />
          Volver a reportes
        </Link>
        {article && !editing && (
          <div role="group" aria-label="Acciones del reporte" className="flex gap-2">
            <Button type="button" variant="outline" size="lg" onClick={startEditing}>
              <Pencil aria-hidden />
              Editar
            </Button>
            <Button type="button" variant="destructive" size="lg" disabled={deleting} onClick={handleDelete}>
              <Trash2 aria-hidden />
              {deleting ? "Eliminando…" : "Eliminar"}
            </Button>
          </div>
        )}
        {article && editing && (
          <div role="group" aria-label="Edición del reporte" className="flex gap-2">
            <Button type="button" variant="outline" size="lg" disabled={saving} onClick={() => setEditing(false)}>
              Cancelar
            </Button>
            <Button type="button" size="lg" disabled={saving} onClick={handleSaveEdit}>
              {saving ? "Guardando…" : "Guardar cambios"}
            </Button>
          </div>
        )}
      </div>

      {editing && (
        <p className="text-sm text-muted-foreground">
          Solo se corrige el análisis (tema, sentimiento, encuadre); título, cuerpo y URL no se
          pueden editar aquí.
        </p>
      )}

      {[
        ["No se pudo guardar", saveError],
        ["No se pudo eliminar", deleteError],
        ["No se pudo cargar", loadError],
      ].map(
        ([title, message]) =>
          message && (
            <Alert key={title} variant="destructive">
              <AlertDescription>
                <strong>{title}.</strong> {message}
              </AlertDescription>
            </Alert>
          )
      )}

      {isLoading && (
        <div className="space-y-2 rounded-lg border p-5">
          <div className="h-6 w-3/4 rounded bg-[var(--surface-3)]" style={{ animation: "odinPulse 1.6s ease-in-out infinite" }} />
          <div className="h-4 w-1/2 rounded bg-[var(--surface-3)]" style={{ animation: "odinPulse 1.6s ease-in-out 0.15s infinite" }} />
        </div>
      )}

      {article && cardValue && (
        <>
          <AnalysisCard
            value={cardValue}
            editable={editing}
            onChange={(patch) => setEditForm((f) => (f ? { ...f, ...patch } : f))}
          />
          <LocalitiesCard articleId={article.id as number} editable={editing} />
          <EntitiesCard entities={article.entities} editable={false} />
          <ArticleBody body={cardValue.body} />
        </>
      )}
    </div>
  )
}
