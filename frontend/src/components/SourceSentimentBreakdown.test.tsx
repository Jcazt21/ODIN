import { describe, expect, it } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"
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

// Siete medios con volumen decreciente: los dos últimos quedan fuera del top 5.
const SEVEN = [
  mention("m1", "Medio 1", "POS", 30),
  mention("m2", "Medio 2", "POS", 20),
  mention("m3", "Medio 3", "NEG", 15),
  mention("m4", "Medio 4", "NEU", 10),
  mention("m5", "Medio 5", "POS", 6),
  mention("m6", "Medio 6", "NEG", 2),
  mention("m7", "Medio 7", "NEU", 1),
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

  it("con 5 medios o menos los muestra todos, sin «N medios más»", () => {
    render(<SourceSentimentBreakdown articles={ARTICLES} />)

    expect(screen.queryByRole("button", { name: /medio/i })).toBeNull()
  })

  it("con más de 5 medios agrupa el resto, por volumen, en «N medios más»", () => {
    render(<SourceSentimentBreakdown articles={SEVEN} />)

    expect(screen.getByRole("button", { name: /2 medios más/i })).toBeTruthy()
  })

  it("«N medios más» se despliega y se pliega", () => {
    render(<SourceSentimentBreakdown articles={SEVEN} />)
    const toggle = screen.getByRole("button", { name: /medios más/i })

    expect(toggle.getAttribute("aria-expanded")).toBe("false")
    fireEvent.click(toggle)
    expect(toggle.getAttribute("aria-expanded")).toBe("true")
  })

  it("escribe el % dentro de los segmentos anchos", () => {
    render(<SourceSentimentBreakdown articles={ARTICLES} />)

    const fila = screen.getByText("Listín Diario").closest("li")
    expect(fila?.textContent).toMatch(/100%/)
  })

  it("avisa qué medio se señala con el mouse y al salir lo suelta", () => {
    const calls: Array<string | null> = []
    render(
      <SourceSentimentBreakdown articles={ARTICLES} onActiveSourceChange={(s) => calls.push(s)} />,
    )
    const fila = screen.getByText("Diario Libre").closest("li")!

    fireEvent.pointerEnter(fila, { pointerType: "mouse" })
    fireEvent.pointerLeave(fila, { pointerType: "mouse" })

    expect(calls).toEqual(["diario_libre", null])
  })

  it("al tocar una fila (touch) la activa, y al tocarla otra vez la suelta", () => {
    const calls: Array<string | null> = []
    const { rerender } = render(
      <SourceSentimentBreakdown articles={ARTICLES} activeSource={null} onActiveSourceChange={(s) => calls.push(s)} />,
    )
    const fila = () => screen.getByText("Diario Libre").closest("li")!

    fireEvent.pointerDown(fila(), { pointerType: "touch" })
    fireEvent.click(fila())
    rerender(
      <SourceSentimentBreakdown articles={ARTICLES} activeSource="diario_libre" onActiveSourceChange={(s) => calls.push(s)} />,
    )
    fireEvent.pointerDown(fila(), { pointerType: "touch" })
    fireEvent.click(fila())

    expect(calls).toEqual(["diario_libre", null])
  })
})
