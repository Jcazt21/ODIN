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

/** "2026-08-20" -> "20/08/2026". La API entrega una fecha sin hora
 *  (`analyzed_on` es DATE), así que se parte el string en vez de construir un
 *  `Date`: `new Date("2026-08-20")` se interpreta como UTC y en husos al oeste
 *  muestra el día anterior. */
export function formatDay(value: string | null | undefined): string {
  if (!value) return "—"
  const [year, month, day] = value.slice(0, 10).split("-")
  return day && month && year ? `${day}/${month}/${year}` : "—"
}

export function isLowConfidence(entity: { extraction_confidence?: number | null }): boolean {
  return typeof entity.extraction_confidence === "number" && entity.extraction_confidence < 0.9
}
