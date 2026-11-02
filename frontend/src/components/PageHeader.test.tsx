import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { PageHeader } from "./PageHeader"

describe("PageHeader", () => {
  it("h1 con el título", () => {
    render(<PageHeader title="Autores" />)
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1)
    expect(screen.getByRole("heading", { level: 1, name: "Autores" })).toBeInTheDocument()
  })

  it("píldora de conteo opcional", () => {
    const { rerender } = render(<PageHeader title="Autores" count="12 autores" />)
    expect(screen.getByText("12 autores")).toBeInTheDocument()
    rerender(<PageHeader title="Autores" />)
    expect(screen.queryByText("12 autores")).not.toBeInTheDocument()
  })

  it("subtítulo opcional", () => {
    const { rerender } = render(<PageHeader title="Analizar" subtitle="Pega el enlace" />)
    expect(screen.getByText("Pega el enlace")).toBeInTheDocument()
    rerender(<PageHeader title="Analizar" />)
    expect(screen.queryByText("Pega el enlace")).not.toBeInTheDocument()
  })
})
