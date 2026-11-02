import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import { SentimentRing } from "@/components/SentimentRing"

describe("SentimentRing", () => {
  it("escribe veredicto y menciones al centro", () => {
    render(
      <SentimentRing positivePct={31} neutralPct={50} negativePct={19} verdict="Neutro" caption="26 menc." />,
    )
    expect(screen.getByText("Neutro")).toBeTruthy()
    expect(screen.getByText("26 menc.")).toBeTruthy()
  })

  it("expone el reparto como texto accesible", () => {
    render(
      <SentimentRing positivePct={31} neutralPct={50} negativePct={19} verdict="Neutro" caption="26 menc." />,
    )
    expect(screen.getByRole("img").getAttribute("aria-label")).toMatch(/31% positivo.*50% neutro.*19% negativo/)
  })

  it("dibuja un arco por categoría con peso y omite las de 0%", () => {
    const { container } = render(
      <SentimentRing positivePct={0} neutralPct={60} negativePct={40} verdict="Neutro" caption="5 menc." />,
    )
    expect(container.querySelectorAll("circle[data-arc]").length).toBe(2)
  })
})
