import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { Pagination, ReportsTable } from "@/components/reports/ReportsTable"
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
    sentiment_score: 0.82,
    framing: "crisis_conflicto",
    has_hard_data: true,
    entity_count: 6,
  },
  {
    id: 2,
    source: "diario_libre",
    url: "https://diariolibre.com/b",
    title: "Reporte automático",
    documentalist: null,
    analyzed_on: null,
    overall_sentiment: "NEU",
    framing: null,
    has_hard_data: false,
    entity_count: 0,
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

describe("ReportsTable — accesibilidad y prioridad de columnas", () => {
  it("el título de cada fila es un link real al detalle", async () => {
    const onOpen = vi.fn()
    renderTable({ onOpen })

    const link = screen.getByRole("link", { name: "Reporte de Juan" })
    expect(link).toHaveAttribute("href", "/reports/1")

    // El clic en la fila sigue abriendo el reporte como atajo de ratón.
    await userEvent.setup().click(screen.getByText("Reporte automático").closest("tr")!)
    expect(onOpen).toHaveBeenCalledWith(2)
  })

  it("las cabeceras van en minúscula normal, sin mayúsculas forzadas", () => {
    renderTable()

    for (const name of ["Fecha", "Fuente", "Sentimiento", "Encuadre", "Analizado"]) {
      const th = screen.getByRole("columnheader", { name })
      expect(th.className).not.toMatch(/uppercase|font-mono/)
    }
  })

  it("las columnas secundarias se ocultan bajo lg", () => {
    renderTable()

    for (const name of ["Encuadre", "Entidades", "Analizado"]) {
      const th = screen.getByRole("columnheader", { name })
      expect(th.className).toContain("hidden")
      expect(th.className).toContain("xl:table-cell")
    }
    expect(screen.getByText("Juan Pérez").closest("td")!.className).toContain("xl:table-cell")
    expect(screen.getByRole("columnheader", { name: "Fecha" }).className).not.toContain("hidden")
  })

  it("el skeleton abarca todas las columnas", () => {
    const { container } = render(
      <MemoryRouter>
        <ReportsTable articles={[]} loading selectedIds={[]} onSelectionChange={vi.fn()} />
      </MemoryRouter>
    )
    const cols = container.querySelectorAll("thead th").length
    expect(container.querySelector("tbody td")).toHaveAttribute("colspan", String(cols))
  })
})

describe("ReportsTable — columnas fusionadas", () => {
  it("tiene siete columnas más el checkbox, sin Datos ni Documentalista", () => {
    renderTable()

    const names = screen.getAllByRole("columnheader").map((th) => th.textContent?.replace(/[↑↓]/g, "").trim())
    expect(names).toEqual(["", "Fecha", "Artículo", "Fuente", "Sentimiento", "Encuadre", "Entidades", "Analizado"])
  })

  it("marca los reportes con datos duros de forma accesible", () => {
    renderTable()

    expect(screen.getAllByText("datos duros")).toHaveLength(1)
  })
})

describe("ReportsTable — sentimiento y encuadre", () => {
  it("muestra el sentimiento como texto con puntaje y barra de tono en la fila", () => {
    renderTable()

    expect(screen.getByText("Negativo")).toBeTruthy()
    expect(screen.getByText("· 82%")).toBeTruthy()
    const row = screen.getByText("Reporte de Juan").closest("tr")!
    expect(row.querySelector("[data-tone='neg']")).toBeTruthy()
    expect(screen.getByText("Negativo").className).not.toMatch(/\bborder\b|\bbg-/)
  })

  it("colorea el encuadre por tono y atenúa la ausencia", () => {
    renderTable()

    expect(screen.getByText("Crisis / conflicto").style.color).toBe("var(--neg)")
    expect(screen.getAllByText("—").length).toBeGreaterThan(0)
  })
})

describe("ReportsTable — fila seleccionada", () => {
  it("marca la fila seleccionada", () => {
    renderTable({ selectedIds: [1] })

    expect(screen.getByText("Reporte de Juan").closest("tr")).toHaveAttribute("aria-selected", "true")
    expect(screen.getByText("Reporte automático").closest("tr")).toHaveAttribute("aria-selected", "false")
  })

  it("seleccionar todos marca todas las filas", () => {
    renderTable({ selectedIds: [1, 2] })

    for (const t of ["Reporte de Juan", "Reporte automático"]) {
      expect(screen.getByText(t).closest("tr")).toHaveAttribute("aria-selected", "true")
    }
  })

  it("la celda del checkbox es un label de área amplia", () => {
    renderTable()

    const cb = screen.getByLabelText("Seleccionar Reporte de Juan")
    expect(cb.closest("label")).toBeTruthy()
  })
})

describe("ReportsTable — skeleton", () => {
  it("dibuja seis filas", () => {
    const { container } = render(
      <MemoryRouter>
        <ReportsTable articles={[]} loading selectedIds={[]} onSelectionChange={vi.fn()} />
      </MemoryRouter>
    )
    expect(container.querySelectorAll("tbody tr")).toHaveLength(6)
  })
})

describe("Pagination", () => {
  it("muestra la página y dispara anterior/siguiente", async () => {
    const onPrev = vi.fn()
    const onNext = vi.fn()
    render(<Pagination page={1} total={40} pageSize={12} loaded={12} loading={false} onPrev={onPrev} onNext={onNext} />)
    const user = userEvent.setup()

    expect(screen.getByText(/Página 2 de 4/)).toBeTruthy()
    await user.click(screen.getByRole("button", { name: /Anterior/ }))
    await user.click(screen.getByRole("button", { name: /Siguiente/ }))
    expect(onPrev).toHaveBeenCalledOnce()
    expect(onNext).toHaveBeenCalledOnce()
  })

  it("deshabilita Anterior en la primera página", () => {
    render(<Pagination page={0} total={40} pageSize={12} loaded={12} loading={false} onPrev={vi.fn()} onNext={vi.fn()} />)

    expect(screen.getByRole("button", { name: /Anterior/ })).toBeDisabled()
  })
})
