import { ChevronDown, Search, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Select } from "@/components/ui/select"
import { useId, useMemo, useState } from "react"
import { LocalityCombobox } from "@/components/LocalityCombobox"
import { useLocalityTree } from "@/lib/queries/localities"
import { indexTree } from "@/lib/localities"
import { FRAMING_LABELS, HEADLINE_LABELS, LEAD_LABELS, SENTIMENT_LABELS, SOURCE_LABELS } from "@/lib/labels"
import type { ArticleFilterOptions, ArticleListParams } from "@/lib/odin-api"

export type HardDataFilter = "" | "true" | "false"

const CONTROL =
  "h-9 w-full rounded-lg border bg-[var(--surface)] px-2.5 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"

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
    <label className="flex h-9 items-center gap-1.5 rounded-lg border bg-[var(--surface)] px-2.5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <input
        type="date"
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="flex-1 bg-transparent text-sm outline-none"
      />
    </label>
  )
}

function Chip({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <span className="odin-pop inline-flex h-7 items-center gap-1 rounded-full bg-[var(--accent-soft)] pr-1 pl-3 text-xs text-primary">
      {label}
      <button
        type="button"
        aria-label={`Quitar filtro ${label}`}
        onClick={onRemove}
        className="inline-flex size-5 items-center justify-center rounded-full text-primary transition-colors duration-150 hover:bg-[var(--accent-border)]"
      >
        <X aria-hidden className="size-3" />
      </button>
    </span>
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
  // El árbol completo son ~204 nodos y se cachea sin vencimiento, así que
  // aplanarlo acá no cuesta una petición por render.
  const topicFieldId = useId()
  const topicListId = `${topicFieldId}-list`
  const panelId = `${topicFieldId}-advanced`
  const { data: tree } = useLocalityTree()
  const { entries } = useMemo(() => indexTree(tree ?? []), [tree])
  const selectedLocality = entries.find((e) => e.id === filters.locality)

  const advancedActive =
    hardData !== "" ||
    [
      filters.entity,
      filters.locality,
      filters.topic,
      filters.framing,
      filters.headline_intent,
      filters.lead_orientation,
      filters.source_quality,
      filters.documentalist,
    ].some((v) => v !== undefined && v !== "")
  const [expanded, setExpanded] = useState(advancedActive)

  const chips: { label: string; onRemove: () => void }[] = []
  const addChip = (name: string, value: string | undefined, patch: Partial<ArticleListParams>) => {
    if (value) chips.push({ label: `${name}: ${value}`, onRemove: () => onChange(patch) })
  }
  addChip("Fuente", facets?.sources.find((x) => x.value === filters.source)?.label ?? filters.source, { source: undefined })
  addChip("Sentimiento", filters.sentiment && (SENTIMENT_LABELS[filters.sentiment] ?? filters.sentiment), { sentiment: undefined })
  addChip("Desde", filters.date_from, { date_from: undefined })
  addChip("Hasta", filters.date_to, { date_to: undefined })
  addChip("Entidad", filters.entity, { entity: undefined })
  addChip("Lugar", filters.locality !== undefined ? (selectedLocality?.name ?? String(filters.locality)) : undefined, { locality: undefined })
  addChip("Tema", filters.topic, { topic: undefined })
  addChip("Encuadre", filters.framing && (FRAMING_LABELS[filters.framing] ?? filters.framing), { framing: undefined })
  addChip("Titular", filters.headline_intent && (HEADLINE_LABELS[filters.headline_intent] ?? filters.headline_intent), { headline_intent: undefined })
  addChip("Lead", filters.lead_orientation && (LEAD_LABELS[filters.lead_orientation] ?? filters.lead_orientation), { lead_orientation: undefined })
  addChip("Calidad de fuente", filters.source_quality && (SOURCE_LABELS[filters.source_quality] ?? filters.source_quality), { source_quality: undefined })
  addChip(
    "Documentalista",
    filters.documentalist !== undefined
      ? (facets?.documentalists.find((a) => a.id === filters.documentalist)?.display_name ?? String(filters.documentalist))
      : undefined,
    { documentalist: undefined }
  )
  if (hardData !== "") {
    chips.push({
      label: `Datos duros: ${hardData === "true" ? "con" : "sin"}`,
      onRemove: () => onHardDataChange(""),
    })
  }

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">Reportes</h1>
        <p className="inline-flex h-7 items-center rounded-full bg-[var(--accent-soft)] px-3 text-sm text-primary">
          {loaded} de {total} reportes
        </p>
      </div>

      {/* items-start: los iconos posicionados a top-1/2 de su envoltorio caen
          por debajo del control si la grilla estira las celdas. */}
      <div className="flex flex-wrap items-start gap-2">
        <div className="relative min-w-[220px] flex-1">
          <Search aria-hidden className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-[var(--faint)]" />
          <input
            aria-label="Buscar reportes"
            value={filters.q ?? ""}
            onChange={(e) => onChange({ q: e.target.value || undefined })}
            placeholder="Título o tema…"
            className={`${CONTROL} pl-8`}
          />
        </div>
        <Select
          aria-label="Fuente"
          className="w-44"
          value={filters.source ?? ""}
          onChange={(e) => onChange({ source: e.target.value || undefined })}
        >
          <option value="">Todas las fuentes</option>
          {facets?.sources.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </Select>
        <Select
          aria-label="Sentimiento"
          className="w-40"
          value={filters.sentiment ?? ""}
          onChange={(e) => onChange({ sentiment: e.target.value || undefined })}
        >
          <option value="">Todo sentimiento</option>
          {(facets?.sentiments ?? []).map((s) => (
            <option key={s} value={s}>
              {SENTIMENT_LABELS[s] ?? s}
            </option>
          ))}
        </Select>
        <DateField label="Desde" value={filters.date_from ?? ""} onChange={(v) => onChange({ date_from: v || undefined })} />
        <DateField label="Hasta" value={filters.date_to ?? ""} onChange={(v) => onChange({ date_to: v || undefined })} />
        <Button
          type="button"
          variant="outline"
          size="lg"
          aria-expanded={expanded}
          aria-controls={panelId}
          onClick={() => setExpanded((v) => !v)}
        >
          Más filtros
          <ChevronDown aria-hidden className={`transition-transform duration-200 ease-[var(--ease-out)] ${expanded ? "rotate-180" : ""}`} />
        </Button>
      </div>

      {expanded && (
        <div
          id={panelId}
          className="odin-pop grid origin-top items-start gap-2.5 rounded-xl border bg-[var(--surface)] p-3 shadow-[var(--shadow-sm)]"
          style={{ gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))" }}
        >
          <div className="relative">
            <Search aria-hidden className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-[var(--faint)]" />
            <input
              aria-label="Entidad mencionada"
              value={filters.entity ?? ""}
              onChange={(e) => onChange({ entity: e.target.value || undefined })}
              placeholder="Entidad mencionada…"
              className={`${CONTROL} pl-8`}
            />
          </div>

          {/* Texto libre CON sugerencias, igual que el campo Tema del formulario
              manual: `main_topic` no está normalizado mientras no exista el
              catálogo administrable (R4), así que un desplegable cerrado dejaría
              fuera cualquier variante que no esté en la lista. */}
          <div className="relative">
            <Search aria-hidden className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-[var(--faint)]" />
            <label htmlFor={topicFieldId} className="sr-only">
              Tema
            </label>
            <input
              id={topicFieldId}
              list={topicListId}
              value={filters.topic ?? ""}
              onChange={(e) => onChange({ topic: e.target.value || undefined })}
              placeholder="Todos los temas"
              className={`${CONTROL} pl-8`}
            />
            <datalist id={topicListId}>
              {(facets?.topics ?? []).map((t) => (
                <option key={t.id} value={t.name} />
              ))}
            </datalist>
          </div>

          <LocalityCombobox
            label="Lugar"
            hideLabel
            entries={entries}
            selected={selectedLocality}
            onSelect={(entry) => onChange({ locality: entry?.id })}
            placeholder="Todos los lugares"
          />

          <Select aria-label="Encuadre" value={filters.framing ?? ""} onChange={(e) => onChange({ framing: e.target.value || undefined })}>
            <option value="">Todo encuadre</option>
            {(facets?.framing ?? []).map((v) => (
              <option key={v} value={v}>
                {FRAMING_LABELS[v] ?? v}
              </option>
            ))}
          </Select>
          <Select
            aria-label="Titular"
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
            aria-label="Lead"
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
            aria-label="Calidad de fuente"
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
          <Select aria-label="Datos duros" value={hardData} onChange={(e) => onHardDataChange(e.target.value as HardDataFilter)}>
            <option value="">Datos duros: todos</option>
            <option value="true">Con datos duros</option>
            <option value="false">Sin datos duros</option>
          </Select>
          <Select
            aria-label="Documentalista"
            value={filters.documentalist === undefined ? "" : String(filters.documentalist)}
            onChange={(e) =>
              onChange({ documentalist: e.target.value ? Number(e.target.value) : undefined })
            }
          >
            <option value="">Todo documentalista</option>
            {(facets?.documentalists ?? []).map((a) => (
              <option key={a.id} value={String(a.id)}>
                {a.display_name}
              </option>
            ))}
          </Select>
        </div>
      )}

      {/* Fuera de la grilla y solo con el filtro puesto: el roll-up por
          subárbol sorprende justo cuando hay un lugar elegido. */}
      {selectedLocality && (
        <p className="text-xs text-muted-foreground">
          {selectedLocality.name} incluye lo marcado en sus municipios.
        </p>
      )}

      {(chips.length > 0 || hasActiveFilters) && (
        <div className="flex flex-wrap items-center gap-1.5">
          {chips.map((chip) => (
            <Chip key={chip.label} {...chip} />
          ))}
          {hasActiveFilters && (
            <button
              type="button"
              onClick={onReset}
              className="ml-1 text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
            >
              Limpiar
            </button>
          )}
        </div>
      )}
    </section>
  )
}
