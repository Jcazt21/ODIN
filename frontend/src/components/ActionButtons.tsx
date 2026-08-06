export function ActionButtons({
  onDiscard,
  onSave,
  saving,
}: {
  onDiscard: () => void
  onSave: () => void
  saving: boolean
}) {
  return (
    <div className="flex items-center gap-2.5">
      <button
        type="button"
        onClick={onDiscard}
        className="rounded-lg border px-3.5 py-2 text-[13px]"
        style={{ borderColor: "var(--border)", color: "var(--neg)" }}
      >
        Descartar
      </button>
      <button
        type="button"
        disabled={saving}
        onClick={onSave}
        className="rounded-lg px-4 py-2 text-[13px] font-semibold disabled:opacity-60"
        style={{ background: "var(--primary)", color: "var(--accent-fg)" }}
      >
        {saving ? "Guardando…" : "Guardar reporte"}
      </button>
    </div>
  )
}
