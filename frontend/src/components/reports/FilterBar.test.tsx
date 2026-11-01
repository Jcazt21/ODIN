import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
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
  sources: [{ value: "acento", label: "Acento" }],
  topics: [],
  sections: [],
  sentiments: ["POS", "NEG"],
  framing: ["CONFLICT"],
  headline_intent: [],
  lead_orientation: [],
  source_quality: [],
  documentalists: [],
} as unknown as ArticleFilterOptions

function setup(filters: ArticleListParams = {}, hasActiveFilters = false) {
  const onChange = vi.fn()
  const onReset = vi.fn()
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <FilterBar
        filters={filters}
        onChange={onChange}
        hardData=""
        onHardDataChange={vi.fn()}
        facets={FACETS}
        onReset={onReset}
        hasActiveFilters={hasActiveFilters}
        total={30}
        loaded={12}
      />
    </QueryClientProvider>
  )
  return { onChange, onReset, user: userEvent.setup() }
}

describe("FilterBar — filtros progresivos", () => {
  it("por defecto solo muestra buscador, fuente, sentimiento y fecha", () => {
    setup()
    expect(screen.getByRole("textbox", { name: /buscar/i })).toBeInTheDocument()
    expect(screen.getByRole("combobox", { name: /fuente/i })).toBeInTheDocument()
    expect(screen.getByRole("combobox", { name: /sentimiento/i })).toBeInTheDocument()
    expect(screen.getByLabelText(/desde/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/hasta/i)).toBeInTheDocument()
    expect(screen.queryByLabelText(/tema/i)).not.toBeInTheDocument()
    expect(screen.queryByRole("combobox", { name: /encuadre/i })).not.toBeInTheDocument()
  })

  it("«Más filtros» revela los avanzados y se puede volver a ocultar", async () => {
    const { user } = setup()
    const toggle = screen.getByRole("button", { name: /más filtros/i })
    expect(toggle).toHaveAttribute("aria-expanded", "false")
    await user.click(toggle)
    expect(toggle).toHaveAttribute("aria-expanded", "true")
    for (const name of [/encuadre/i, /titular/i, /lead/i, /calidad/i, /datos duros/i, /documentalista/i]) {
      expect(screen.getByRole("combobox", { name })).toBeInTheDocument()
    }
    expect(screen.getByLabelText(/tema/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/entidad/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/lugar/i)).toBeInTheDocument()
  })

  it("con un filtro avanzado activo el panel arranca abierto", () => {
    setup({ framing: "CONFLICT" }, true)
    expect(screen.getByRole("button", { name: /más filtros/i })).toHaveAttribute("aria-expanded", "true")
    expect(screen.getByRole("combobox", { name: /encuadre/i })).toBeInTheDocument()
  })

  it("cada filtro activo es un chip removible y Limpiar lo resetea todo", async () => {
    const { user, onChange, onReset } = setup({ source: "acento" }, true)
    await user.click(screen.getByRole("button", { name: /quitar .*fuente/i }))
    expect(onChange).toHaveBeenCalledWith({ source: undefined })
    await user.click(screen.getByRole("button", { name: /^limpiar/i }))
    expect(onReset).toHaveBeenCalledTimes(1)
  })

  it("emite el mismo patch de siempre al cambiar un filtro", async () => {
    const { user, onChange } = setup()
    await user.selectOptions(screen.getByRole("combobox", { name: /sentimiento/i }), "POS")
    expect(onChange).toHaveBeenCalledWith({ sentiment: "POS" })
  })

  it("muestra el conteo en una sola línea de resultados", () => {
    setup()
    expect(screen.getAllByText(/12 de 30/)).toHaveLength(1)
  })
})
