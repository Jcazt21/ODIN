import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
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
    framing: "crisis_conflicto",
    documentalist: "Ana Reyes",
    analyzed_on: "2026-08-20",
    overall_sentiment: "NEG",
  },
] as unknown as ArticleSummary[]

describe("ReportsTable — etiqueta de encuadre", () => {
  it("es texto plano traducido, sin caja con borde que se parta en líneas", () => {
    /* Antes era un `<span>` con fondo y borde que, al saltar de línea, se
       dibujaba como dos rectángulos desfasados. Sin caja el problema no existe;
       el test fija que no vuelva. */
    render(
      <MemoryRouter>
        <ReportsTable articles={ROWS} selectedIds={[]} onSelectionChange={vi.fn()} />
      </MemoryRouter>
    )

    const label = screen.getByText(/crisis/i)
    expect(label.className).not.toMatch(/\bborder\b|\bbg-/)
  })
})
