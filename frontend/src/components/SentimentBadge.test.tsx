import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import { SentimentBadge } from "@/components/SentimentBadge"

describe("SentimentBadge", () => {
  it("falls back to neutral for a null sentiment", () => {
    render(<SentimentBadge sentiment={null} />)
    expect(screen.getByText("Neutro")).toBeInTheDocument()
  })

  it("shows the score as a percentage for a non-neutral sentiment", () => {
    render(<SentimentBadge sentiment="POS" score={0.823} />)
    expect(screen.getByText(/82%/)).toBeInTheDocument()
  })

  it("omits the score for a neutral sentiment even if one is given", () => {
    render(<SentimentBadge sentiment="NEU" score={0.5} />)
    expect(screen.queryByText(/%/)).not.toBeInTheDocument()
  })
})
