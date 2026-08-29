import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import { SourceSentimentBreakdown } from "@/components/SourceSentimentBreakdown"
import type { CanonicalEntityArticleMention } from "@/lib/odin-api"

function mention(source: string, sourceName: string, sentiment: string, count: number) {
  return {
    article_id: Math.random(),
    title: "t",
    url: "u",
    source,
    source_name: sourceName,
    published_at: null,
    sentiment_toward: sentiment,
    sentiment_score: 1,
    mentions_count: count,
  } as unknown as CanonicalEntityArticleMention
}

// Refleja el reparto real de Luis Abinader: dos medios bien cubiertos y uno
// que se apoya en una sola nota.
const ARTICLES = [
  mention("diario_libre", "Diario Libre", "POS", 20),
  mention("diario_libre", "Diario Libre", "NEG", 8),
  mention("listin_diario", "Listín Diario", "POS", 17),
  mention("acento", "Acento", "NEG", 1),
]

describe("SourceSentimentBreakdown", () => {
  it("lista un renglón por medio, con su nombre legible", () => {
    render(<SourceSentimentBreakdown articles={ARTICLES} />)

    for (const name of ["Diario Libre", "Listín Diario", "Acento"]) {
      expect(screen.getByText(name)).toBeTruthy()
    }
  })

  it("marca al medio que se apoya en muy pocas menciones", () => {
    render(<SourceSentimentBreakdown articles={ARTICLES} />)

    const fila = screen.getByText("Acento").closest("li")
    expect(fila?.textContent).toMatch(/muestra baja/i)
  })

  it("no marca al que está bien respaldado", () => {
    render(<SourceSentimentBreakdown articles={ARTICLES} />)

    const fila = screen.getByText("Diario Libre").closest("li")
    expect(fila?.textContent).not.toMatch(/muestra baja/i)
  })

  it("muestra cuántas menciones sostienen cada renglón", () => {
    /* Sin el volumen a la vista, un 100% de una nota se lee igual que uno de
       veinte. */
    render(<SourceSentimentBreakdown articles={ARTICLES} />)

    expect(screen.getByText("Diario Libre").closest("li")?.textContent).toMatch(/28/)
    expect(screen.getByText("Acento").closest("li")?.textContent).toMatch(/1/)
  })

  it("no dibuja nada si no hay menciones con sentimiento", () => {
    const { container } = render(<SourceSentimentBreakdown articles={[]} />)

    expect(container).toBeEmptyDOMElement()
  })
})
