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
  it("es una caja propia y no una etiqueta en línea", () => {
    /* Un `<span>` en línea con fondo y borde reparte una caja redondeada POR
       CADA línea cuando el texto salta: "Crisis / conflicto" se veía como dos
       rectángulos desfasados. jsdom no calcula cajas de línea, así que se
       verifica la propiedad que lo evita. */
    render(
      <MemoryRouter>
        <ReportsTable articles={ROWS} selectedIds={[]} onSelectionChange={vi.fn()} />
      </MemoryRouter>
    )

    const badge = screen.getByText(/crisis/i)
    expect(badge.className).toContain("inline-block")
  })
})
