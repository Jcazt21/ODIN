import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { SentimentDot } from "./SentimentDot"

describe("SentimentDot", () => {
  it("muestra punto y texto, nunca solo color", () => {
    const { container } = render(<SentimentDot sentiment="POS" score={0.82} />)
    expect(screen.getByText("Positivo")).toBeInTheDocument()
    expect(screen.getByText(/82%/)).toBeInTheDocument()
    expect(container.querySelector("[aria-hidden]")).not.toBeNull()
  })

  it("usa el tono del sentimiento", () => {
    const { container } = render(<SentimentDot sentiment="NEG" />)
    expect((container.firstChild as HTMLElement).style.color).toBe("var(--neg)")
  })

  it("sin sentimiento cae a neutro", () => {
    render(<SentimentDot sentiment={null} score={0.5} />)
    expect(screen.getByText("Neutro")).toBeInTheDocument()
    expect(screen.queryByText(/50%/)).not.toBeInTheDocument()
  })
})
