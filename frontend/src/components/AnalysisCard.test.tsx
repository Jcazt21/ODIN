import { describe, expect, it } from "vitest"
import { render, screen, within } from "@testing-library/react"
import { AnalysisCard, type AnalysisCardFields } from "@/components/AnalysisCard"

/** Lo mínimo que la card necesita; cada test sobreescribe lo que le importa. */
function fields(patch: Partial<AnalysisCardFields> = {}): AnalysisCardFields {
  return {
    title: "Apagones desde temprano",
    url: "https://acento.com.do/nota",
    source: "acento",
    source_name: "Acento",
    authors: null,
    section: null,
    published_at: null,
    body: null,
    main_topic: null,
    topic_keywords: null,
    overall_sentiment: null,
    sentiment_score: null,
    framing: null,
    headline_intent: null,
    lead_orientation: null,
    source_quality: null,
    has_hard_data: null,
    dominant_actor: null,
    blamed_actor: null,
    credited_actor: null,
    ...patch,
  }
}

describe("AnalysisCard: documentalista", () => {
  it("shows who filed the report, ahead of the source", () => {
    render(<AnalysisCard value={fields({ documentalist: "Jean Azar" })} editable={false} />)

    expect(screen.getByText("Jean Azar")).toBeInTheDocument()
    // El orden es parte del pedido: primero quién lo documentó, después el medio.
    const row = screen.getByText("Documentalista").parentElement!.parentElement!
    expect(row.textContent!.indexOf("Documentalista")).toBeLessThan(
      row.textContent!.indexOf("Fuente"),
    )
  })

  it("reads a report with no documentalist as crawled, not as missing data", () => {
    render(<AnalysisCard value={fields({ documentalist: null })} editable={false} />)

    expect(screen.getByText("Automático")).toBeInTheDocument()
  })

  it("omits the line entirely in the analyze preview, where nothing is filed yet", () => {
    // AnalyzePage arma la card desde /api/analyze, que no manda el campo:
    // ahí no hay reporte guardado y "Automático" sería mentira.
    render(<AnalysisCard value={fields()} editable={false} />)

    expect(screen.queryByText("Documentalista")).not.toBeInTheDocument()
    expect(screen.queryByText("Automático")).not.toBeInTheDocument()
  })
})

describe("AnalysisCard: lectura sin envoltorios visuales", () => {
  it("conserva sentimiento editable, título enlazado, encuadre y actores", () => {
    render(
      <AnalysisCard
        value={fields({ framing: "CONFLICT", overall_sentiment: "NEG", dominant_actor: "Gobierno" })}
        editable
      />,
    )

    expect(screen.getByRole("link", { name: "Apagones desde temprano" })).toHaveAttribute(
      "href",
      "https://acento.com.do/nota",
    )
    for (const s of ["NEG", "NEU", "POS"]) expect(screen.getByRole("button", { name: s })).toBeInTheDocument()
    for (const label of ["Marco narrativo", "Intención del titular", "Actor dominante", "Actor señalado"]) {
      expect(screen.getByText(label)).toBeInTheDocument()
    }
    expect(screen.getByDisplayValue("Gobierno")).toBeInTheDocument()
  })

  it("el cuerpo del artículo ya no vive dentro de la card (va aparte, al final)", () => {
    render(<AnalysisCard value={fields({ body: "Texto del cuerpo" })} editable={false} />)
    expect(screen.queryByText("Texto del cuerpo")).not.toBeInTheDocument()
    expect(screen.queryByText("Cuerpo del artículo")).not.toBeInTheDocument()
  })

  it("el resultado se lee en fichas: encuadre, calidad de fuentes y datos duros", () => {
    render(
      <AnalysisCard
        value={fields({ framing: "CONFLICT", source_quality: "MIXED", has_hard_data: true })}
        editable={false}
      />,
    )
    const tiles = screen.getByRole("list", { name: "Resultado del análisis" })
    const labels = Array.from(tiles.querySelectorAll("li")).map((li) => li.querySelector("p")!.textContent)
    expect(labels).toEqual([
      "Marco narrativo",
      "Intención del titular",
      "Orientación del lead",
      "Calidad de fuentes",
      "Datos duros",
    ])
    expect(within(tiles).getByText("Sí")).toBeInTheDocument()
  })

  it("los actores sin dato se atenúan en vez de competir con los reales", () => {
    render(<AnalysisCard value={fields({ dominant_actor: "Gobierno" })} editable={false} />)
    expect(screen.getByText("Gobierno")).not.toHaveClass("text-[var(--faint)]")
    expect(screen.getAllByText("—").every((el) => el.className.includes("text-[var(--faint)]"))).toBe(true)
  })

  it("no se dibuja como tarjeta de vidrio", () => {
    const { container } = render(<AnalysisCard value={fields()} editable={false} />)
    expect(container.querySelector(".odin-glass, .odin-glass-strong")).toBeNull()
  })
})
