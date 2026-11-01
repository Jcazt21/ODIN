import { ChevronLeft, ChevronRight } from "lucide-react"
import { Link } from "react-router-dom"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { SentimentDot, SENTIMENT_TONE } from "@/components/reports/SentimentDot"
import { FRAMING_LABELS, toneOf, toneVars } from "@/lib/labels"
import { formatDateShort, formatDay } from "@/lib/format"
import type { ArticleSummary } from "@/lib/odin-api"

export type SortField = "published_at" | "source" | "analyzed_on"
export type SortOrder = "asc" | "desc"

const HEADER_CLASS = "border-b px-3.5 py-2.5 text-left text-xs font-medium whitespace-nowrap text-muted-foreground"
/** Columnas secundarias: en pantallas angostas la tabla se queda con lo esencial. */
const SECONDARY = "hidden xl:table-cell"

function PlainHeader({ children, className }: { children: React.ReactNode; className?: string }) {
  return <th className={cn(HEADER_CLASS, className)}>{children}</th>
}

/** Cabecera que ordena. Un `<button>` y no un `<th onClick>`: así se alcanza
 *  con teclado y los lectores de pantalla lo anuncian como accionable. El
 *  `aria-sort` va en el `<th>`, que es donde lo espera la especificación. */
function SortableHeader({
  label,
  field,
  sort,
  order,
  onSort,
  className,
}: {
  label: string
  field: SortField
  sort: SortField
  order: SortOrder
  onSort?: (field: SortField, order: SortOrder) => void
  className?: string
}) {
  const active = sort === field
  return (
    <th
      className={cn(HEADER_CLASS, active && "text-primary", className)}
      aria-sort={active ? (order === "asc" ? "ascending" : "descending") : "none"}
    >
      <button
        type="button"
        // Cambiar de columna arranca en descendente (lo más reciente o lo
        // último alfabéticamente primero); volver a pulsar la activa invierte.
        onClick={() => onSort?.(field, active && order === "desc" ? "asc" : "desc")}
        className="inline-flex cursor-pointer items-center gap-1 font-[inherit] select-none"
      >
        {label}
        {active && <span aria-hidden>{order === "desc" ? "↓" : "↑"}</span>}
      </button>
    </th>
  )
}

/** Celdas con altura pareja y centradas: las filas de 1 y 3 líneas se leen igual. */
const CELL = "px-3.5 py-3 align-middle whitespace-nowrap"
const COLUMNS = 8
const SKELETON_WIDTHS = ["w-3/4", "w-2/3", "w-5/6", "w-1/2", "w-4/5", "w-3/5"]

export function ReportsTable({
  articles,
  loading = false,
  onOpen,
  sort = "published_at",
  order = "desc",
  onSort,
  selectedIds,
  onSelectionChange,
}: {
  articles: ArticleSummary[]
  loading?: boolean
  onOpen?: (id: number) => void
  sort?: SortField
  order?: SortOrder
  onSort?: (field: SortField, order: SortOrder) => void
  selectedIds: number[]
  onSelectionChange: (ids: number[]) => void
}) {
  return (
    <div className="overflow-x-auto rounded-xl border bg-[var(--surface)]">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="bg-muted/50">
            <th className="w-11 border-b p-0">
              <label className="flex size-11 cursor-pointer items-center justify-center">
                <input
                  type="checkbox"
                  aria-label="Seleccionar todos"
                  checked={articles.length > 0 && selectedIds.length === articles.length}
                  onChange={(e) =>
                    onSelectionChange(e.target.checked ? articles.map((a) => a.id as number) : [])
                  }
                />
              </label>
            </th>
            <SortableHeader label="Fecha" field="published_at" sort={sort} order={order} onSort={onSort} />
            <PlainHeader className="w-full">Artículo</PlainHeader>
            <SortableHeader label="Fuente" field="source" sort={sort} order={order} onSort={onSort} />
            <PlainHeader>Sentimiento</PlainHeader>
            <PlainHeader className={SECONDARY}>Encuadre</PlainHeader>
            <PlainHeader className={cn("text-right", SECONDARY)}>Entidades</PlainHeader>
            <SortableHeader label="Analizado" field="analyzed_on" sort={sort} order={order} onSort={onSort} className={SECONDARY} />
          </tr>
        </thead>
        <tbody>
          {loading
            ? Array.from({ length: 6 }).map((_, i) => (
                <tr key={i} className="h-16 border-b">
                  <td className="px-3.5 py-3" colSpan={COLUMNS}>
                    <div
                      className={cn("h-4 rounded bg-[var(--surface-3)]", SKELETON_WIDTHS[i % SKELETON_WIDTHS.length])}
                      style={{ animation: "odinPulse 1.6s ease-in-out infinite" }}
                    />
                  </td>
                </tr>
              ))
            : articles.map((a) => {
                const selected = selectedIds.includes(a.id as number)
                const tone = SENTIMENT_TONE[a.overall_sentiment ?? "NEU"] ?? "neu"
                return (
                  <tr
                    key={a.id}
                    aria-selected={selected}
                    onClick={() => onOpen?.(a.id as number)}
                    className={cn(
                      "h-16 cursor-pointer border-b transition-colors duration-150 ease-out last:border-b-0 hover:bg-muted/60",
                      selected && "bg-[var(--accent-soft)] hover:bg-[var(--accent-soft)]"
                    )}
                  >
                    <td
                      className="relative w-11 p-0"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {/* Barra de tono: permite escanear el sentimiento sin leer; el texto sigue en su columna. */}
                      <span
                        aria-hidden
                        data-tone={tone}
                        className="absolute inset-y-0 left-0 w-[3px]"
                        style={{ background: `var(--${tone})` }}
                      />
                      <label className="flex size-11 cursor-pointer items-center justify-center">
                        <input
                          type="checkbox"
                          aria-label={`Seleccionar ${a.title}`}
                          checked={selected}
                          onChange={(e) =>
                            onSelectionChange(
                              e.target.checked
                                ? [...selectedIds, a.id as number]
                                : selectedIds.filter((id) => id !== a.id)
                            )
                          }
                        />
                      </label>
                    </td>
                    <td className={cn(CELL, "font-mono text-xs text-[var(--faint)]")}>
                      {formatDateShort(a.published_at)}
                    </td>
                    <td className="px-3.5 py-3 align-middle">
                      <Link
                        to={`/reports/${a.id}`}
                        // El clic ya navega por el enlace; sin esto también dispararía el de la fila.
                        onClick={(e) => e.stopPropagation()}
                        className="font-medium leading-snug outline-none hover:underline focus-visible:underline"
                      >
                        {a.title}
                      </Link>
                      {a.main_topic && (
                        <p className="mt-0.5 text-xs text-muted-foreground capitalize">{a.main_topic}</p>
                      )}
                    </td>
                    <td className={cn(CELL, "text-muted-foreground")}>{a.source_name || a.source}</td>
                    <td className={CELL}>
                      <SentimentDot sentiment={a.overall_sentiment} score={a.sentiment_score} />
                    </td>
                    <td className={cn(CELL, SECONDARY)}>
                      {a.framing ? (
                        <span
                          className="text-xs font-medium"
                          style={{ color: toneVars(toneOf(a.framing)).color }}
                        >
                          {FRAMING_LABELS[a.framing] ?? a.framing}
                        </span>
                      ) : (
                        <span className="text-[var(--faint)]">—</span>
                      )}
                    </td>
                    <td className={cn(CELL, "text-right", SECONDARY)}>
                      <span className="font-mono text-muted-foreground">{a.entity_count}</span>
                      {a.has_hard_data && (
                        <p className="mt-0.5 text-[11px] text-primary">
                          <span aria-hidden>● </span>
                          <span>datos duros</span>
                        </p>
                      )}
                    </td>
                    <td className={cn(CELL, SECONDARY)}>
                      <p className="font-mono text-xs text-[var(--faint)]">{formatDay(a.analyzed_on)}</p>
                      <p className="mt-0.5 text-[11px] text-[var(--faint)]">{a.documentalist ?? "Automático"}</p>
                    </td>
                  </tr>
                )
              })}
        </tbody>
      </table>
    </div>
  )
}

export function Pagination({
  page,
  total,
  pageSize,
  loaded,
  loading,
  onPrev,
  onNext,
}: {
  page: number
  total: number
  pageSize: number
  loaded: number
  loading: boolean
  onPrev: () => void
  onNext: () => void
}) {
  const to = Math.min(total, (page + 1) * pageSize)
  if (total <= pageSize) return null
  return (
    <div className="flex items-center justify-between rounded-xl border bg-[var(--surface-2)] px-3.5 py-2.5">
      <span className="text-xs text-[var(--faint)]">
        Página {page + 1} de {Math.max(1, Math.ceil(total / pageSize))} · {loaded} visibles
      </span>
      <div className="flex items-center gap-2">
        <Button variant="outline" size="lg" disabled={page === 0 || loading} onClick={onPrev}>
          <ChevronLeft />
          Anterior
        </Button>
        <Button variant="outline" size="lg" disabled={to >= total || loading} onClick={onNext}>
          Siguiente
          <ChevronRight />
        </Button>
      </div>
    </div>
  )
}
