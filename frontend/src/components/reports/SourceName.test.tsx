import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { ReportsTable } from "@/components/reports/ReportsTable"
import { FilterBar } from "@/components/reports/FilterBar"
import type { ArticleFilterOptions, ArticleSummary } from "@/lib/odin-api"

const ROWS = [
  {
    id: 1,
    source: "listin_diario",
    source_name: "Listín Diario",
    url: "https://listindiario.com/a",
    title: "Reporte de Juan",
    documentalist: "Juan Pérez",
    analyzed_on: "2026-08-20",
    overall_sentiment: "NEG",
  },
] as unknown as ArticleSummary[]

describe("ReportsTable — nombre del medio", () => {
  it("muestra el nombre legible del medio, no el slug", () => {
    render(
      <MemoryRouter>
        <ReportsTable articles={ROWS} selectedIds={[]} onSelectionChange={vi.fn()} />
      </MemoryRouter>
    )

    expect(screen.getByText("Listín Diario")).toBeTruthy()
    expect(screen.queryByText("listin_diario")).toBeNull()
  })
})

const FACETS = {
  sources: [
    { value: "listin_diario", label: "Listín Diario" },
    { value: "diario_libre", label: "Diario Libre" },
  ],
  sections: [],
  sentiments: [],
  framing: [],
  headline_intent: [],
  lead_orientation: [],
  source_quality: [],
  documentalists: [],
} as unknown as ArticleFilterOptions

describe("FilterBar — desplegable de medios", () => {
  it("muestra la etiqueta pero filtra por el slug", () => {
    // FilterBar consulta el árbol de lugares para su filtro geográfico.
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={queryClient}>
      <FilterBar
        filters={{}}
        onChange={vi.fn()}
        hardData=""
        onHardDataChange={vi.fn()}
        facets={FACETS}
        onReset={vi.fn()}
        hasActiveFilters={false}
        total={0}
        loaded={0}
      />
      </QueryClientProvider>
    )

    const option = screen.getByRole("option", { name: "Listín Diario" }) as HTMLOptionElement
    expect(option.value).toBe("listin_diario")
  })
})
