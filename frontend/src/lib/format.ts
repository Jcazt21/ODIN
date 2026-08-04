const MONTHS_SHORT = [
  "ene", "feb", "mar", "abr", "may", "jun",
  "jul", "ago", "sep", "oct", "nov", "dic",
]

/** Formato compacto de tabla: "27 jul 26". */
export function formatDateShort(value: string | null | undefined): string {
  if (!value) return "—"
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  const day = String(d.getDate()).padStart(2, "0")
  const month = MONTHS_SHORT[d.getMonth()]
  const year = String(d.getFullYear()).slice(-2)
  return `${day} ${month} ${year}`
}

/** Formato completo: cabecera de artículo, artículos vinculados de una entidad. */
export function formatDateFull(value: string | null | undefined): string {
  if (!value) return "Fecha desconocida"
  try {
    return new Intl.DateTimeFormat("es-DO", {
      dateStyle: "long",
      timeStyle: "short",
    }).format(new Date(value))
  } catch {
    return value
  }
}

export function isLowConfidence(entity: { extraction_confidence?: number | null }): boolean {
  return typeof entity.extraction_confidence === "number" && entity.extraction_confidence < 0.9
}
