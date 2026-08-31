import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
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
