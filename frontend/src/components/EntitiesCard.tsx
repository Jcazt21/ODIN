import { useState } from "react"
import { Pencil, Trash2 } from "lucide-react"
import { Select } from "@/components/ui/select"
import { SentimentBadge } from "@/components/SentimentBadge"
import { SentimentSegmented } from "@/components/SentimentSegmented"
import { ENTITY_TYPE_LABELS } from "@/lib/labels"
import { isLowConfidence } from "@/lib/format"

// Forma mínima independiente del schema del backend, no `EntityAnalysis`
// (`EntityMention`, entidad ya guardada con `id` real): esta tarjeta también
// muestra entidades de la vista previa de /api/analyze (`AnalyzePreviewEntity`,
// `id` posiblemente `null`), y no usa `id`/`canonical_entity_id` para nada —
// igual criterio que `AnalysisCardFields` en AnalysisCard.tsx.
export interface EntityFields {
  name: string
  type: string
  mentions_count: number
  sentiment_toward: string | null
  sentiment_score: number | null
  context: string | null
  extraction_confidence: number
}

export function EntitiesCard({
  entities,
  editable,
  onUpdate,
  onRemove,
}: {
  entities: EntityFields[]
  editable: boolean
  onUpdate?: (index: number, patch: Partial<EntityFields>) => void
  onRemove?: (index: number) => void
}) {
  const [editingIndex, setEditingIndex] = useState<number | null>(null)

  return (
    <div
      className="odin-glass overflow-hidden rounded-xl border px-6 py-5"
      style={{ boxShadow: "var(--shadow-sm)" }}
    >
      <div className="mb-3 flex items-baseline gap-2">
        <h3 className="text-[15px] font-semibold">Figuras y empresas mencionadas</h3>
        <span className="font-mono text-[11px]" style={{ color: "var(--faint)" }}>
          {entities.length} detectadas
        </span>
      </div>

      {entities.length === 0 ? (
        <p className="text-[13px]" style={{ color: "var(--muted-foreground)" }}>
          No se detectaron figuras públicas ni empresas en este artículo.
        </p>
      ) : (
        <div className="grid gap-3" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))" }}>
          {entities.map((ent, i) => {
            const isEditing = editable && editingIndex === i
            return (
              <div
                key={`${ent.type}-${ent.name}-${i}`}
                className="space-y-[9px] rounded-[9px] border p-3.5"
                style={{ background: "var(--surface-2)", borderColor: "var(--border)" }}
              >
                <div className="flex items-center gap-2">
                  {isEditing ? (
                    <input
                      value={ent.name}
                      onChange={(e) => onUpdate?.(i, { name: e.target.value })}
                      className="h-8 flex-1 rounded-[7px] border border-dashed bg-transparent px-2 text-[14px] font-semibold outline-none"
                      style={{ borderColor: "var(--border-strong)" }}
                    />
                  ) : (
                    <span className="flex-1 text-[14px] font-semibold">{ent.name}</span>
                  )}
                  {isLowConfidence(ent) && (
                    <span
                      title="Confianza de extracción baja — revisar"
                      className="inline-block rounded-[5px] border px-1.5 py-0.5 text-[10.5px] font-semibold"
                      style={{ background: "var(--warn-soft)", borderColor: "var(--warn)", color: "var(--warn)" }}
                    >
                      revisar
                    </span>
                  )}
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  {isEditing ? (
                    <Select
                      dashed
                      className="h-7 w-auto text-xs"
                      value={ent.type}
                      onChange={(e) => onUpdate?.(i, { type: e.target.value as "PERSON" | "ORG" })}
                    >
                      <option value="PERSON">Persona</option>
                      <option value="ORG">Organización</option>
                    </Select>
                  ) : (
                    <span className="text-[11.5px]" style={{ color: "var(--faint)" }}>
                      {ENTITY_TYPE_LABELS[ent.type] ?? ent.type}
                    </span>
                  )}
                  <span className="font-mono text-[11.5px]" style={{ color: "var(--faint)" }}>
                    {ent.mentions_count} {ent.mentions_count === 1 ? "mención" : "menciones"}
                  </span>
                  <span className="flex-1" />
                  {isEditing ? (
                    <SentimentSegmented
                      value={(ent.sentiment_toward as "POS" | "NEG" | "NEU" | null) ?? "NEU"}
                      onChange={(v) => onUpdate?.(i, { sentiment_toward: v })}
                      size="sm"
                    />
                  ) : (
                    <SentimentBadge sentiment={ent.sentiment_toward} score={ent.sentiment_score} />
                  )}
                </div>

                {ent.context && (
                  <blockquote
                    className="border-l-2 pl-[11px] text-[12.5px] leading-[1.55] italic text-pretty"
                    style={{ borderColor: "var(--border-strong)", color: "var(--muted-foreground)" }}
                  >
                    “{ent.context}”
                  </blockquote>
                )}

                {editable && (
                  <div className="flex justify-end gap-1.5 pt-1">
                    {isEditing ? (
                      <button
                        type="button"
                        onClick={() => setEditingIndex(null)}
                        className="rounded-[6px] border px-2 py-1 text-[11.5px]"
                        style={{ background: "var(--surface)", borderColor: "var(--border)" }}
                      >
                        Listo
                      </button>
                    ) : (
                      <button
                        type="button"
                        onClick={() => setEditingIndex(i)}
                        aria-label="Editar entidad"
                        className="inline-flex items-center gap-1 rounded-[6px] border px-2 py-1 text-[11.5px]"
                        style={{ background: "var(--surface)", borderColor: "var(--border)" }}
                      >
                        <Pencil className="size-3" />
                        Editar
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => {
                        onRemove?.(i)
                        setEditingIndex((prev) => {
                          if (prev === null || prev === i) return null
                          return prev > i ? prev - 1 : prev
                        })
                      }}
                      aria-label="Quitar entidad"
                      className="inline-flex items-center gap-1 rounded-[6px] border px-2 py-1 text-[11.5px] transition-colors hover:text-[var(--neg)]"
                      style={{ background: "var(--surface)", borderColor: "var(--border)" }}
                    >
                      <Trash2 className="size-3" />
                      Quitar
                    </button>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
