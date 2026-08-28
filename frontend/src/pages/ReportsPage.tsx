import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { FilterBar, type HardDataFilter } from "@/components/reports/FilterBar"
import { ReportsTable, Pagination } from "@/components/reports/ReportsTable"
import { useArticleFilterOptions, useArticles } from "@/lib/queries/articles"
import { useExportArticles } from "@/lib/queries/documentalists"
import { OdinApiError, type ArticleListParams } from "@/lib/odin-api"

const PAGE_SIZE = 12
// El orden se maneja desde las cabeceras de la tabla, no desde la barra de
// filtros: dos controles para lo mismo se contradicen en cuanto uno cambia.
const EMPTY_FILTERS: ArticleListParams = { sort: "published_at", order: "desc" }

/** Debounce solo de los campos de texto libre (q, entity): clicks en selects,
 *  fechas, orden o paginación deben reflejarse de inmediato — antes heredaban
 *  los mismos 300ms de espera del texto y se sentían lentos. */
function useDebouncedTextFilters(filters: ArticleListParams): ArticleListParams {
  const [debounced, setDebounced] = useState(filters)
  useEffect(() => {
    const textChanged = filters.q !== debounced.q || filters.entity !== debounced.entity
    if (!textChanged) {
      setDebounced(filters)
      return
    }
    const t = setTimeout(() => setDebounced(filters), 300)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters])
  return debounced
}

export function ReportsPage() {
  const navigate = useNavigate()
  const [filters, setFilters] = useState<ArticleListParams>(EMPTY_FILTERS)
  const [hardData, setHardData] = useState<HardDataFilter>("")
  const [page, setPage] = useState(0)
  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const exportMutation = useExportArticles()

  const debouncedFilters = useDebouncedTextFilters(filters)

  // Limpiar la selección cuando cambian los filtros: evita exportar reportes
  // que ya no están a la vista.
  useEffect(() => {
    setSelectedIds([])
  }, [filters])

  const { data: facets } = useArticleFilterOptions()
  const { data, isLoading, isFetching, error } = useArticles({
    ...debouncedFilters,
    has_hard_data: hardData === "" ? undefined : hardData === "true",
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  })

  function updateFilters(patch: Partial<ArticleListParams>) {
    setPage(0)
    setFilters((f) => ({ ...f, ...patch }))
  }

  function updateHardData(v: HardDataFilter) {
    setPage(0)
    setHardData(v)
  }

  function resetFilters() {
    setPage(0)
    setFilters(EMPTY_FILTERS)
    setHardData("")
  }

  const hasActiveFilters =
    hardData !== "" || Object.entries(filters).some(([k, v]) => k !== "sort" && v !== undefined && v !== "")

  const total = data?.total ?? 0
  const items = data?.items ?? []
  const loading = isLoading || isFetching
  const errorMessage = error instanceof OdinApiError ? error.message : error ? "No se pudo conectar con la API de Odin." : null

  return (
    <div className="flex w-full flex-col gap-4">
      <FilterBar
        filters={filters}
        onChange={updateFilters}
        hardData={hardData}
        onHardDataChange={updateHardData}
        facets={facets}
        onReset={resetFilters}
        hasActiveFilters={hasActiveFilters}
        total={total}
        loaded={items.length}
      />

      {errorMessage && (
        <div role="alert" className="rounded-[7px] border px-3 py-2.5 text-[12.5px]" style={{ background: "var(--neg-soft)", borderColor: "var(--neg)", color: "var(--neg)" }}>
          {errorMessage}
        </div>
      )}

      {!loading && items.length === 0 ? (
        <div
          className="odin-glass flex flex-col items-center gap-3 rounded-xl border py-14 text-center"
        >
          <p className="text-[14.5px] font-semibold">Sin resultados</p>
          <p className="max-w-[38ch] text-[13px]" style={{ color: "var(--muted-foreground)" }}>
            Ningún reporte coincide con los filtros aplicados.
          </p>
          {hasActiveFilters && (
            <button
              type="button"
              onClick={resetFilters}
              className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-[13px]"
              style={{ borderColor: "var(--border)" }}
            >
              <X className="size-3.5" />
              Quitar filtros
            </button>
          )}
        </div>
      ) : (
        <>
          {selectedIds.length > 0 && (
            <div
              className="mb-2 flex items-center gap-3 rounded-[7px] border px-3 py-2"
              style={{ background: "var(--surface-2)", borderColor: "var(--border)" }}
            >
              <span className="text-[12.5px]">
                {selectedIds.length} {selectedIds.length === 1 ? "reporte" : "reportes"} seleccionados
              </span>
              <Button
                type="button"
                onClick={() => exportMutation.mutate(selectedIds)}
                disabled={exportMutation.isPending}
              >
                {exportMutation.isPending ? "Exportando…" : "Exportar a Word"}
              </Button>
              <button
                type="button"
                onClick={() => setSelectedIds([])}
                className="text-[12px] underline-offset-2 hover:underline"
                style={{ color: "var(--faint)" }}
              >
                Limpiar selección
              </button>
              {exportMutation.error && (
                <span role="alert" className="text-[12px]" style={{ color: "var(--neg)" }}>
                  No se pudo exportar.
                </span>
              )}
            </div>
          )}
          <ReportsTable
            articles={items}
            loading={loading}
            onOpen={(id) => navigate(`/reports/${id}`)}
            sort={filters.sort ?? "published_at"}
            order={filters.order ?? "desc"}
            onSort={(sort, order) => updateFilters({ sort, order })}
            selectedIds={selectedIds}
            onSelectionChange={setSelectedIds}
          />
        </>
      )}

      <Pagination
        page={page}
        total={total}
        pageSize={PAGE_SIZE}
        loaded={items.length}
        loading={loading}
        onPrev={() => setPage((p) => Math.max(0, p - 1))}
        onNext={() => setPage((p) => p + 1)}
      />
    </div>
  )
}
