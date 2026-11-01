import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { MemoryRouter } from "react-router-dom"
import { ReportsPage } from "@/pages/ReportsPage"
import * as articlesQueries from "@/lib/queries/articles"
import * as documentalistQueries from "@/lib/queries/documentalists"
import * as odinApi from "@/lib/odin-api"

vi.mock("@/lib/odin-api", async () => {
  const actual = await vi.importActual<typeof odinApi>("@/lib/odin-api")
  return { ...actual, getLocalityTree: vi.fn().mockResolvedValue([]) }
})
vi.mock("@/lib/queries/articles")
vi.mock("@/lib/queries/documentalists")

const ITEMS = [
  { id: 1, source: "acento", title: "Primer reporte", overall_sentiment: "POS", entity_count: 0 },
  { id: 2, source: "acento", title: "Segundo reporte", overall_sentiment: "NEG", entity_count: 0 },
]

const exportMutate = vi.fn()
let exportError: Error | null = null

function mockList(items: unknown[]) {
  vi.mocked(articlesQueries.useArticles).mockReturnValue({
    data: { items, total: items.length },
    isLoading: false,
    isFetching: false,
    error: null,
  } as never)
}

function renderPage() {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>
    </QueryClientProvider>
  )
  return userEvent.setup()
}

beforeEach(() => {
  exportMutate.mockReset()
  exportError = null
  vi.mocked(articlesQueries.useArticleFilterOptions).mockReturnValue({ data: undefined } as never)
  vi.mocked(documentalistQueries.useExportArticles).mockImplementation(
    () => ({ mutate: exportMutate, isPending: false, error: exportError }) as never
  )
  mockList(ITEMS)
})

describe("ReportsPage — selección y exportación", () => {
  it("con reportes seleccionados muestra la barra y exporta los ids", async () => {
    const user = renderPage()
    await user.click(screen.getByLabelText("Seleccionar Primer reporte"))
    await user.click(screen.getByLabelText("Seleccionar Segundo reporte"))

    expect(screen.getByText(/2 seleccionados/i)).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: /exportar a word/i }))
    expect(exportMutate).toHaveBeenCalledWith([1, 2])

    await user.click(screen.getByRole("button", { name: /^limpiar$/i }))
    expect(screen.queryByText(/seleccionados/i)).not.toBeInTheDocument()
  })

  it("un error al exportar se anuncia como alerta", async () => {
    exportError = new Error("boom")
    const user = renderPage()
    await user.click(screen.getByLabelText("Seleccionar Primer reporte"))

    expect(screen.getByRole("alert")).toHaveTextContent(/no se pudo exportar/i)
  })
})

describe("ReportsPage — sin resultados", () => {
  it("con filtros ofrece quitarlos", async () => {
    mockList([])
    const user = renderPage()
    await user.type(screen.getByRole("textbox", { name: /buscar/i }), "zzz")

    await user.click(screen.getByRole("button", { name: /quitar filtros/i }))
    expect(screen.getByRole("textbox", { name: /buscar/i })).toHaveValue("")
  })

  it("sin filtros invita a analizar un artículo", () => {
    mockList([])
    renderPage()
    expect(screen.getByRole("link", { name: /analizar un artículo/i })).toHaveAttribute("href", "/analyze")
  })
})
