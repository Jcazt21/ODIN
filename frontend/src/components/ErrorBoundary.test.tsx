import { describe, expect, it } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { ErrorBoundary } from "@/components/ErrorBoundary"

function Bomb(): never {
  throw new Error("boom")
}

describe("ErrorBoundary", () => {
  it("renders children when nothing throws", () => {
    render(
      <ErrorBoundary>
        <p>todo bien</p>
      </ErrorBoundary>
    )
    expect(screen.getByText("todo bien")).toBeInTheDocument()
  })

  it("catches a thrown error and shows the fallback with the message", () => {
    render(
      <ErrorBoundary>
        <Bomb />
      </ErrorBoundary>
    )
    expect(screen.getByRole("alert")).toBeInTheDocument()
    expect(screen.getByText("boom")).toBeInTheDocument()
  })

  it("clears the error when retrying, remounting children", () => {
    let shouldThrow = true
    function Flaky() {
      if (shouldThrow) throw new Error("boom")
      return <p>recuperado</p>
    }
    render(
      <ErrorBoundary>
        <Flaky />
      </ErrorBoundary>
    )
    expect(screen.getByRole("alert")).toBeInTheDocument()
    shouldThrow = false
    fireEvent.click(screen.getByRole("button", { name: /reintentar/i }))
    expect(screen.getByText("recuperado")).toBeInTheDocument()
  })
})
