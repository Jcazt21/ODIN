import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { ReportsTable } from "@/components/reports/ReportsTable"
import type { ArticleSummary } from "@/lib/odin-api"

const ROWS = [
  {
    id: 1,
    source: "listin_diario",
    url: "https://listindiario.com/a",
    title: "Reporte de Juan",
    documentalist: "Juan Pérez",
    analyzed_on: "2026-08-20",
    overall_sentiment: "NEG",
  },
  {
    id: 2,
    source: "diario_libre",
    url: "https://diariolibre.com/b",
    title: "Reporte automático",
    documentalist: null,
    analyzed_on: null,
    overall_sentiment: "NEU",
  },
] as unknown as ArticleSummary[]

function renderTable(props: Record<string, unknown> = {}) {
  const onSelectionChange = vi.fn()
  render(
    <MemoryRouter>
      <ReportsTable
        articles={ROWS}
        selectedIds={[]}
        onSelectionChange={onSelectionChange}
        {...props}
      />
    </MemoryRouter>
  )
  return onSelectionChange
}

describe("ReportsTable — documentalista y selección", () => {
  it("muestra el documentalista de cada reporte", () => {
    renderTable()

    expect(screen.getByText("Juan Pérez")).toBeTruthy()
  })

  it("muestra la fecha de análisis en día/mes/año", () => {
    renderTable()

    expect(screen.getByText("20/08/2026")).toBeTruthy()
  })

  it("marca como automático lo que no tiene documentalista", () => {
    renderTable()

    expect(screen.getByText("Automático")).toBeTruthy()
  })

  it("permite seleccionar un reporte", async () => {
    const onSelectionChange = renderTable()
    const user = userEvent.setup()

    await user.click(screen.getByLabelText("Seleccionar Reporte de Juan"))

    expect(onSelectionChange).toHaveBeenCalledWith([1])
  })

  it("selecciona y deselecciona todo de una vez", async () => {
    const onSelectionChange = renderTable()
    const user = userEvent.setup()

    await user.click(screen.getByLabelText("Seleccionar todos"))

    expect(onSelectionChange).toHaveBeenCalledWith([1, 2])
  })
})
