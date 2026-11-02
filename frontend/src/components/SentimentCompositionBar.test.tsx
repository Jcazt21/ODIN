import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import { SentimentCompositionBar } from "@/components/SentimentCompositionBar"
import type { SentimentAggregate } from "@/lib/sentiment-aggregate"

const AGG = {
  positivePct: 31,
  neutralPct: 50,
  negativePct: 19,
  dominant: "NEU",
  lowSample: false,
  sampleSize: 20,
} as unknown as SentimentAggregate

describe("SentimentCompositionBar", () => {
  it("escribe la leyenda con texto, no solo color", () => {
    render(<SentimentCompositionBar aggregate={AGG} />)

    expect(screen.getByText("31% positivo")).toBeTruthy()
    expect(screen.getByText("50% neutro")).toBeTruthy()
    expect(screen.getByText("19% negativo")).toBeTruthy()
  })

  it("muestra el veredicto dominante al centro del anillo", () => {
    render(<SentimentCompositionBar aggregate={AGG} />)

    expect(screen.getByText("Neutro")).toBeTruthy()
  })

  it("rotula el alcance: Global, o el medio señalado", () => {
    const { rerender } = render(<SentimentCompositionBar aggregate={AGG} />)
    expect(screen.getByText("Global")).toBeTruthy()

    rerender(<SentimentCompositionBar aggregate={AGG} scopeLabel="Diario Libre" />)
    expect(screen.getByText("Diario Libre")).toBeTruthy()
  })

  it("al señalar un medio muestra su logo junto al nombre; en Global no hay logo", () => {
    const { container, rerender } = render(<SentimentCompositionBar aggregate={AGG} />)
    expect(container.querySelector("img")).toBeNull()

    rerender(
      <SentimentCompositionBar aggregate={AGG} scopeLabel="Diario Libre" scopeSource="diario_libre" />,
    )
    expect(container.querySelector("img")).not.toBeNull()
  })
})
