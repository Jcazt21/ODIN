import { Link } from "react-router-dom"
import { Button, buttonVariants } from "@/components/ui/button"

interface ActionButtonsProps {
  /** `draft`: vista previa editable; `saved`: ya existe en el archivo. */
  state: "draft" | "saved"
  reportId?: number
  saving?: boolean
  onSave: () => void
  onDiscard: () => void
  onAnalyzeAnother: () => void
}

/** Barra inferior única del flujo de Analizar: estado a la izquierda, acciones a la derecha. */
export function ActionButtons({
  state,
  reportId,
  saving = false,
  onSave,
  onDiscard,
  onAnalyzeAnother,
}: ActionButtonsProps) {
  const isDraft = state === "draft"
  return (
    <div className="odin-enter sticky bottom-4 z-30 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-[var(--surface)] px-4 py-3 shadow-[var(--shadow)]">
      <span className="flex items-center gap-2 text-sm">
        <span
          aria-hidden
          className="size-2 rounded-full"
          style={{ background: isDraft ? "var(--primary)" : "var(--pos)" }}
        />
        {isDraft ? "Vista previa · sin guardar" : "Guardado en el archivo"}
      </span>
      <div className="flex items-center gap-2">
        {isDraft ? (
          <>
            <Button type="button" variant="outline" size="lg" onClick={onDiscard}>
              Descartar
            </Button>
            <Button type="button" size="lg" disabled={saving} onClick={onSave}>
              {saving ? "Guardando…" : "Guardar reporte"}
            </Button>
          </>
        ) : (
          <>
            <Button type="button" variant="outline" size="lg" onClick={onAnalyzeAnother}>
              Analizar otro
            </Button>
            {reportId !== undefined && (
              <Link to={`/reports/${reportId}`} className={buttonVariants({ size: "lg" })}>
                Ver reporte
              </Link>
            )}
          </>
        )}
      </div>
    </div>
  )
}
