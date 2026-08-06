import { RotateCcw, Search } from "lucide-react"
import { Select } from "@/components/ui/select"
import { FRAMING_LABELS, HEADLINE_LABELS, LEAD_LABELS, SENTIMENT_LABELS, SOURCE_LABELS } from "@/lib/labels"
import type { ArticleFilterOptions, ArticleListParams } from "@/lib/odin-api"

export type HardDataFilter = "" | "true" | "false"

function DateField({
  label,
  value,
  onChange,
}: {
  label: string
  value: string
  onChange: (v: string) => void
}) {
  return (
    <label
      className="flex h-8 items-center gap-1.5 rounded-[7px] border px-[11px]"
      style={{ background: "var(--surface-2)", borderColor: "var(--border)" }}
    >
      <span className="text-[11.5px]" style={{ color: "var(--faint)" }}>
        {label}
      </span>
      <input
        type="date"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="flex-1 bg-transparent text-[12.5px] outline-none"
      />
    </label>
  )
}

export function FilterBar({
  filters,
  onChange,
  hardData,
  onHardDataChange,
  facets,
  onReset,
  hasActiveFilters,
  total,
  loaded,
}: {
  filters: ArticleListParams
  onChange: (patch: Partial<ArticleListParams>) => void
  hardData: HardDataFilter
  onHardDataChange: (v: HardDataFilter) => void
  facets: ArticleFilterOptions | null | undefined
  onReset: () => void
  hasActiveFilters: boolean
  total: number
  loaded: number
}) {
  return (
    <div
      className="rounded-xl border p-[18px]"
      style={{ background: "var(--panel)", borderColor: "var(--border)", boxShadow: "var(--shadow-sm)" }}
    >
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <div className="flex items-baseline gap-2.5">
          <h1 className="text-[19px] font-semibold">Reportes</h1>
          <span className="text-[12.5px]" style={{ color: "var(--faint)" }}>
            {loaded} de {total} reportes
          </span>
        </div>
        {hasActiveFilters && (
          <button
            type="button"
            onClick={onReset}
            className="inline-flex items-center gap-1.5 text-[12.5px]"
            style={{ color: "var(--muted-foreground)" }}
          >
            <RotateCcw className="size-3.5" />
            Limpiar filtros
          </button>
        )}
      </div>

      <div className="grid gap-[10px]" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(168px, 1fr))" }}>
        <div className="relative">
          <Search className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2" style={{ color: "var(--faint)" }} />
          <input
            value={filters.q ?? ""}
            onChange={(e) => onChange({ q: e.target.value || undefined })}
            placeholder="Título o tema…"
            className="h-8 w-full rounded-[7px] border pr-2 pl-8 text-[13px] outline-none"
            style={{ background: "var(--surface-2)", borderColor: "var(--border)" }}
          />
        </div>
        <div className="relative">
          <Search className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2" style={{ color: "var(--faint)" }} />
          <input
            value={filters.entity ?? ""}
            onChange={(e) => onChange({ entity: e.target.value || undefined })}
            placeholder="Entidad mencionada…"
            className="h-8 w-full rounded-[7px] border pr-2 pl-8 text-[13px] outline-none"
            style={{ background: "var(--surface-2)", borderColor: "var(--border)" }}
          />
        </div>

        <Select value={filters.source ?? ""} onChange={(e) => onChange({ source: e.target.value || undefined })}>
          <option value="">Todas las fuentes</option>
          {facets?.sources.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </Select>
        <Select value={filters.sentiment ?? ""} onChange={(e) => onChange({ sentiment: e.target.value || undefined })}>
          <option value="">Todo sentimiento</option>
          {(facets?.sentiments ?? []).map((s) => (
            <option key={s} value={s}>
              {SENTIMENT_LABELS[s] ?? s}
            </option>
          ))}
        </Select>
        <Select value={filters.framing ?? ""} onChange={(e) => onChange({ framing: e.target.value || undefined })}>
          <option value="">Todo encuadre</option>
          {(facets?.framing ?? []).map((v) => (
            <option key={v} value={v}>
              {FRAMING_LABELS[v] ?? v}
            </option>
          ))}
        </Select>
        <Select
          value={filters.headline_intent ?? ""}
          onChange={(e) => onChange({ headline_intent: e.target.value || undefined })}
        >
          <option value="">Todo titular</option>
          {(facets?.headline_intent ?? []).map((v) => (
            <option key={v} value={v}>
              {HEADLINE_LABELS[v] ?? v}
            </option>
          ))}
        </Select>
        <Select
          value={filters.lead_orientation ?? ""}
          onChange={(e) => onChange({ lead_orientation: e.target.value || undefined })}
        >
          <option value="">Todo lead</option>
          {(facets?.lead_orientation ?? []).map((v) => (
            <option key={v} value={v}>
              {LEAD_LABELS[v] ?? v}
            </option>
          ))}
        </Select>
        <Select
          value={filters.source_quality ?? ""}
          onChange={(e) => onChange({ source_quality: e.target.value || undefined })}
        >
          <option value="">Toda calidad de fuente</option>
          {(facets?.source_quality ?? []).map((v) => (
            <option key={v} value={v}>
              {SOURCE_LABELS[v] ?? v}
            </option>
          ))}
        </Select>
        <Select value={hardData} onChange={(e) => onHardDataChange(e.target.value as HardDataFilter)}>
          <option value="">Datos duros: todos</option>
          <option value="true">Con datos duros</option>
          <option value="false">Sin datos duros</option>
        </Select>
        <DateField label="Desde" value={filters.date_from ?? ""} onChange={(v) => onChange({ date_from: v || undefined })} />
        <DateField label="Hasta" value={filters.date_to ?? ""} onChange={(v) => onChange({ date_to: v || undefined })} />
        <Select value={filters.sort ?? "recent"} onChange={(e) => onChange({ sort: e.target.value as "recent" | "oldest" })}>
          <option value="recent">Más recientes</option>
          <option value="oldest">Más antiguos</option>
        </Select>
      </div>
    </div>
  )
}
