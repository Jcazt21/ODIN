import { useEffect, useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { X } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button, buttonVariants } from "@/components/ui/button"
import { FilterBar, type HardDataFilter } from "@/components/reports/FilterBar"
import { ReportsTable, Pagination } from "@/components/reports/ReportsTable"
import { useArticleFilterOptions, useArticles } from "@/lib/queries/articles"
import { useDebouncedTextFilters } from "@/lib/use-debounced-text-filters"
import { useExportArticles } from "@/lib/queries/documentalists"
import { OdinApiError, type ArticleListParams } from "@/lib/odin-api"

const PAGE_SIZE = 12
// El orden se maneja desde las cabeceras de la tabla, no desde la barra de
// filtros: dos controles para lo mismo se contradicen en cuanto uno cambia.
const EMPTY_FILTERS: ArticleListParams = { sort: "published_at", order: "desc" }

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
    hardData !== "" || Object.entries(filters).some(
      ([k, v]) => k !== "sort" && k !== "order" && v !== undefined && v !== ""
    )

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
        <Alert variant="destructive">
          <AlertDescription>{errorMessage}</AlertDescription>
        </Alert>
      )}

      {!loading && items.length === 0 ? (
        <div className="flex flex-col items-center gap-3 rounded-xl border bg-[var(--surface)] py-14 text-center">
          <p className="text-base font-semibold">Sin resultados</p>
          <p className="max-w-[38ch] text-sm text-muted-foreground">
            {hasActiveFilters
              ? "Ningún reporte coincide con los filtros aplicados."
              : "Todavía no hay reportes guardados."}
          </p>
          {hasActiveFilters ? (
            <Button type="button" variant="outline" size="lg" onClick={resetFilters}>
              <X aria-hidden />
              Quitar filtros
            </Button>
          ) : (
            <Link to="/analyze" className={buttonVariants({ size: "lg" })}>
              Analizar un artículo
            </Link>
          )}
        </div>
      ) : (
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
      )}

      {selectedIds.length > 0 && (
        <div className="odin-enter sticky bottom-4 z-30 flex flex-wrap items-center gap-3 rounded-xl bg-[var(--surface)] px-4 py-3 shadow-[var(--shadow)]">
          <span className="text-sm">
            {selectedIds.length} {selectedIds.length === 1 ? "seleccionado" : "seleccionados"}
          </span>
          <Button
            type="button"
            size="lg"
            onClick={() => exportMutation.mutate(selectedIds)}
            disabled={exportMutation.isPending}
          >
            {exportMutation.isPending ? "Exportando…" : "Exportar a Word"}
          </Button>
          <Button type="button" variant="ghost" size="lg" onClick={() => setSelectedIds([])}>
            Limpiar
          </Button>
          {exportMutation.error && (
            <Alert variant="destructive" className="w-auto flex-1 basis-60">
              <AlertDescription>No se pudo exportar.</AlertDescription>
            </Alert>
          )}
        </div>
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
