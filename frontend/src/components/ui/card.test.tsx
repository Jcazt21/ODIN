import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { Badge } from "./badge"
import { Card, CardContent, CardTitle } from "./card"

describe("Card", () => {
  it("renderiza su contenido sin la clase de vidrio", () => {
    render(
      <Card>
        <CardTitle>Resumen</CardTitle>
        <CardContent>Cuerpo</CardContent>
      </Card>
    )
    expect(screen.getByText("Resumen")).toBeInTheDocument()
    expect(screen.getByText("Cuerpo").closest("[data-slot=card]")).not.toHaveClass("odin-glass")
  })
})

describe("Badge chip", () => {
  it("la variante chip muestra su texto", () => {
    render(<Badge variant="chip">12 de 67 reportes</Badge>)
    expect(screen.getByText("12 de 67 reportes")).toHaveAttribute("data-variant", "chip")
  })
})
