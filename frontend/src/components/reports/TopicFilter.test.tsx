import { describe, expect, it, vi } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { FilterBar } from "@/components/reports/FilterBar"
import type { ArticleFilterOptions, ArticleListParams } from "@/lib/odin-api"
import * as odinApi from "@/lib/odin-api"

vi.mock("@/lib/odin-api", async () => {
  const actual = await vi.importActual<typeof odinApi>("@/lib/odin-api")
  return { ...actual, getLocalityTree: vi.fn().mockResolvedValue([]) }
})

const FACETS = {
  sources: [],
  topics: ["policía nacional", "banco central"],
  sections: [],
  sentiments: [],
  framing: [],
  headline_intent: [],
  lead_orientation: [],
  source_quality: [],
  documentalists: [],
} as unknown as ArticleFilterOptions

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

describe("FilterBar — filtro por tema", () => {
  it("emite el tema escrito", async () => {
    /* El input es controlado por `filters`, que acá no se actualiza porque
       `onChange` es un espía: se parte de lo ya escrito y se agrega la última
       letra, que es lo que realmente ocurre tecla a tecla en la página. */
    const user = userEvent.setup()
    const onChange = renderBar({ topic: "policí" })

    await user.type(await screen.findByLabelText(/tema/i), "a")

    await waitFor(() => expect(onChange).toHaveBeenCalledWith({ topic: "policía" }))
  })

  it("sugiere los temas ya usados, sin encerrar al usuario en ellos", async () => {
    /* Texto libre con sugerencias, igual que el campo Tema del formulario
       manual: `main_topic` no está normalizado, así que un desplegable cerrado
       dejaría fuera cualquier variante que no esté en la lista. */
    renderBar()

    const tema = await screen.findByLabelText(/tema/i)
    expect(tema.tagName).toBe("INPUT")
    const sugerencias = document.getElementById(tema.getAttribute("list") ?? "")
    expect(sugerencias?.querySelectorAll("option").length).toBe(2)
  })

  it("limpia el filtro cuando se vacía la caja", async () => {
    /* Un string vacío en la URL filtraría por "" en vez de no filtrar. */
    const user = userEvent.setup()
    const onChange = renderBar({ topic: "policía" })

    await user.clear(await screen.findByLabelText(/tema/i))

    await waitFor(() => expect(onChange).toHaveBeenCalledWith({ topic: undefined }))
  })
})
