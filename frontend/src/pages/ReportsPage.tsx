import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { X } from "lucide-react"
import { FilterBar, type HardDataFilter } from "@/components/reports/FilterBar"
import { ReportsTable, Pagination } from "@/components/reports/ReportsTable"
import { useArticleFilterOptions, useArticles } from "@/lib/queries/articles"
import { OdinApiError, type ArticleListParams } from "@/lib/odin-api"

const PAGE_SIZE = 12
const EMPTY_FILTERS: ArticleListParams = { sort: "recent" }

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

  const debouncedFilters = useDebouncedTextFilters(filters)

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
          className="flex flex-col items-center gap-3 rounded-xl border py-14 text-center"
          style={{ borderColor: "var(--border)", background: "var(--panel)" }}
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
        <ReportsTable
          items={items}
          loading={loading}
          onOpen={(id) => navigate(`/reports/${id}`)}
          sortDir={filters.sort ?? "recent"}
          onToggleSort={() => updateFilters({ sort: filters.sort === "oldest" ? "recent" : "oldest" })}
        />
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
