import { useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { ChevronLeft, Pencil, Trash2 } from "lucide-react"
import { AnalysisCard, type AnalysisCardFields } from "@/components/AnalysisCard"
import { EntitiesCard } from "@/components/EntitiesCard"
import { useConfirm } from "@/lib/dialog"
import { useArticle, useUpdateArticle, useDeleteArticle } from "@/lib/queries/articles"
import { OdinApiError, type ArticleAnalysis, type ArticleUpdatePayload } from "@/lib/odin-api"

type EditableFields = Pick<
  AnalysisCardFields,
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
    <div className="flex w-full flex-col gap-4">
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex items-center gap-1.5 text-[13px]"
          style={{ color: "var(--muted-foreground)" }}
        >
          <ChevronLeft className="size-3.5" />
          Volver a la lista
        </button>
        {article && !editing && (
          <div className="flex gap-2">
            <button
              type="button"
              onClick={startEditing}
              className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-[13px]"
              style={{ borderColor: "var(--border)" }}
            >
              <Pencil className="size-3.5" />
              Editar
            </button>
            <button
              type="button"
              disabled={deleting}
              onClick={handleDelete}
              className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-[13px] disabled:opacity-60"
              style={{ borderColor: "var(--border)", color: "var(--neg)" }}
            >
              <Trash2 className="size-3.5" />
              {deleting ? "Eliminando…" : "Eliminar"}
            </button>
          </div>
        )}
        {article && editing && (
          <div className="flex gap-2">
            <button
              type="button"
              disabled={saving}
              onClick={() => setEditing(false)}
              className="rounded-lg border px-3 py-1.5 text-[13px]"
              style={{ borderColor: "var(--border)" }}
            >
              Cancelar
            </button>
            <button
              type="button"
              disabled={saving}
              onClick={handleSaveEdit}
              className="rounded-lg px-3.5 py-1.5 text-[13px] font-semibold disabled:opacity-60"
              style={{ background: "var(--primary)", color: "var(--accent-fg)" }}
            >
              {saving ? "Guardando…" : "Guardar cambios"}
            </button>
          </div>
        )}
      </div>

      {editing && (
        <p className="text-[12.5px]" style={{ color: "var(--muted-foreground)" }}>
          Solo se corrige el análisis (tema, sentimiento, encuadre); título, cuerpo y URL no se
          pueden editar aquí.
        </p>
      )}

      {saveError && (
        <div role="alert" className="rounded-[7px] border px-3 py-2.5 text-[12.5px]" style={{ background: "var(--neg-soft)", borderColor: "var(--neg)", color: "var(--neg)" }}>
          <strong>No se pudo guardar</strong> {saveError}
        </div>
      )}
      {deleteError && (
        <div role="alert" className="rounded-[7px] border px-3 py-2.5 text-[12.5px]" style={{ background: "var(--neg-soft)", borderColor: "var(--neg)", color: "var(--neg)" }}>
          <strong>No se pudo eliminar</strong> {deleteError}
        </div>
      )}
      {loadError && (
        <div role="alert" className="rounded-[7px] border px-3 py-2.5 text-[12.5px]" style={{ background: "var(--neg-soft)", borderColor: "var(--neg)", color: "var(--neg)" }}>
          <strong>No se pudo cargar</strong> {loadError}
        </div>
      )}

      {isLoading && (
        <div className="space-y-2 rounded-xl border p-[22px]" style={{ borderColor: "var(--border)" }}>
          <div className="h-6 w-3/4 rounded" style={{ background: "var(--surface-3)", animation: "odinPulse 1.6s ease-in-out infinite" }} />
          <div className="h-4 w-1/2 rounded" style={{ background: "var(--surface-3)", animation: "odinPulse 1.6s ease-in-out 0.15s infinite" }} />
        </div>
      )}

      {article && cardValue && (
        <>
          <AnalysisCard
            value={cardValue}
            editable={editing}
            onChange={(patch) => setEditForm((f) => (f ? { ...f, ...patch } : f))}
          />
          <EntitiesCard entities={article.entities} editable={false} />
        </>
      )}
    </div>
  )
}
