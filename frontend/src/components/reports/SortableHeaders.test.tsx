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
    source_name: "Listín Diario",
    url: "https://listindiario.com/a",
    title: "Un reporte",
    documentalist: "Ana Reyes",
    analyzed_on: "2026-08-20",
    overall_sentiment: "NEG",
  },
] as unknown as ArticleSummary[]

function renderTable(props: Record<string, unknown> = {}) {
  const onSort = vi.fn()
  render(
    <MemoryRouter>
      <ReportsTable
        articles={ROWS}
        selectedIds={[]}
        onSelectionChange={vi.fn()}
        sort="published_at"
        order="desc"
        onSort={onSort}
        {...props}
      />
    </MemoryRouter>
  )
  return onSort
}

describe("ReportsTable — cabeceras ordenables", () => {
  it("Fuente y Analizado son botones, como Fecha", () => {
    renderTable()

    for (const name of [/fecha/i, /fuente/i, /analizado/i]) {
      expect(screen.getByRole("button", { name })).toBeTruthy()
    }
  })

  it("las columnas no ordenables siguen sin serlo", () => {
    renderTable()

    expect(screen.queryByRole("button", { name: /encuadre/i })).toBeNull()
    expect(screen.queryByRole("button", { name: /^artículo$/i })).toBeNull()
  })

  it("cambiar de columna arranca en descendente", async () => {
    const user = userEvent.setup()
    const onSort = renderTable()

    await user.click(screen.getByRole("button", { name: /fuente/i }))

    expect(onSort).toHaveBeenCalledWith("source", "desc")
  })

  it("volver a pulsar la columna activa invierte la dirección", async () => {
    const user = userEvent.setup()
    const onSort = renderTable({ sort: "source", order: "desc" })

    await user.click(screen.getByRole("button", { name: /fuente/i }))

    expect(onSort).toHaveBeenCalledWith("source", "asc")
  })

  it("solo la columna activa muestra la flecha", () => {
    renderTable({ sort: "analyzed_on", order: "asc" })

    expect(screen.getByRole("button", { name: /analizado/i }).textContent).toContain("↑")
    expect(screen.getByRole("button", { name: /fecha/i }).textContent).not.toContain("↓")
  })

  it("anuncia el orden a lectores de pantalla", () => {
    renderTable({ sort: "source", order: "asc" })

    expect(
      screen.getByRole("button", { name: /fuente/i }).closest("th")?.getAttribute("aria-sort")
    ).toBe("ascending")
  })
})
