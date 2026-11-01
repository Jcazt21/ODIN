import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { ArticleBody } from "@/components/ArticleBody"

describe("ArticleBody", () => {
  it("empieza cerrado y se abre con 'Leer el artículo completo'", async () => {
    const user = userEvent.setup()
    const { container } = render(<ArticleBody body={"Primer párrafo\nSegundo párrafo"} />)
    const details = container.querySelector("details")!
    expect(details).not.toHaveAttribute("open")

    await user.click(screen.getByText("Leer el artículo completo"))
    expect(details).toHaveAttribute("open")
    expect(screen.getByText("Primer párrafo")).toBeVisible()
    expect(screen.getByText("Segundo párrafo")).toBeInTheDocument()
  })

  it("no dibuja nada si el artículo no tiene cuerpo", () => {
    const { container } = render(<ArticleBody body={null} />)
    expect(container).toBeEmptyDOMElement()
  })

  it("el cuerpo no tiene caja con scroll interno", () => {
    const { container } = render(<ArticleBody body="Texto" />)
    expect(container.querySelector("[class*='max-h-']")).toBeNull()
    expect(container.querySelector("[class*='overflow-auto']")).toBeNull()
  })
})
