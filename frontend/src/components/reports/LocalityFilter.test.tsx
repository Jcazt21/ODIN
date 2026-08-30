import { describe, expect, it, vi, beforeEach } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { FilterBar } from "@/components/reports/FilterBar"
import type { ArticleFilterOptions, ArticleListParams } from "@/lib/odin-api"
import * as odinApi from "@/lib/odin-api"

vi.mock("@/lib/odin-api", async () => {
  const actual = await vi.importActual<typeof odinApi>("@/lib/odin-api")
  return { ...actual, getLocalityTree: vi.fn() }
})

const FACETS = {
  sources: [],
  topics: [],
  sections: [],
  sentiments: [],
  framing: [],
  headline_intent: [],
  lead_orientation: [],
  source_quality: [],
  documentalists: [],
} as unknown as ArticleFilterOptions

const TREE = [
  {
    id: 1,
    name: "República Dominicana",
    level: "PAIS",
    aliases: [],
    children: [
      {
        id: 10,
        name: "Santiago",
        level: "PROVINCIA",
        aliases: [],
        children: [
          { id: 100, name: "Villa Bisonó", level: "MUNICIPIO", aliases: ["Navarrete"], children: [] },
        ],
      },
    ],
  },
]

function renderBar(filters: ArticleListParams = {}) {
  const onChange = vi.fn()
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <FilterBar
        filters={filters}
        onChange={onChange}
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
  return onChange
}

describe("FilterBar — filtro por lugar", () => {
  beforeEach(() => {
    vi.mocked(odinApi.getLocalityTree).mockReset()
    vi.mocked(odinApi.getLocalityTree).mockResolvedValue(TREE as never)
  })

  it("ofrece buscar un lugar", async () => {
    renderBar()

    expect(await screen.findByLabelText(/lugar/i)).toBeTruthy()
  })

  it("filtra por el id del lugar elegido", async () => {
    const user = userEvent.setup()
    const onChange = renderBar()

    await user.type(await screen.findByLabelText(/lugar/i), "Santiago")
    await user.click(await screen.findByText("Santiago"))

    await waitFor(() => expect(onChange).toHaveBeenCalledWith({ locality: 10 }))
  })

  it("encuentra un municipio por su alias", async () => {
    /* El árbol trae los alias justamente para buscar en memoria: quien escribe
       "Navarrete" busca Villa Bisonó. */
    const user = userEvent.setup()
    renderBar()

    await user.type(await screen.findByLabelText(/lugar/i), "Navarrete")

    expect(await screen.findByText(/Villa Bisonó/)).toBeTruthy()
  })

  it("todos los controles de la fila miden lo mismo", async () => {
    /* La grilla estira las celdas a la altura de la más alta. Cuando el filtro
       de lugar traía su etiqueta visible encima, la fila crecía y las lupas y
       los chevrones —anclados a top-1/2 de un envoltorio ya estirado— caían
       por debajo de sus controles. El nombre accesible sigue existiendo. */
    renderBar()

    const lugar = await screen.findByLabelText(/lugar/i)
    // La etiqueta sigue en el DOM para lectores de pantalla, pero oculta a la
    // vista: si ocupara alto, la fila crecería y volvería el desalineo.
    expect(screen.getByText("Lugar").className).toContain("sr-only")
    expect(lugar.getAttribute("aria-label")).toBe("Lugar")
  })

  it("explica el roll-up solo cuando hay un lugar elegido", async () => {
    /* Antes ocupaba dos líneas siempre, empujando la grilla. El aviso importa
       recién cuando el filtro está puesto y los conteos podrían sorprender. */
    renderBar()
    await screen.findByLabelText(/lugar/i)
    expect(screen.queryByText(/incluye/i)).toBeNull()

    renderBar({ locality: 10 })

    expect(await screen.findByText(/incluye/i)).toBeTruthy()
  })
})
