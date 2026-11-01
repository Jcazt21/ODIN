import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { describe, expect, it, vi } from "vitest"
import type { ArticleSummary } from "@/lib/odin-api"
import { ArticleRowsList } from "./ArticleRowsList"

const article = (id: number, title: string) =>
  ({ id, title, published_at: "2026-03-04T12:00:00Z", overall_sentiment: "POS", sentiment_score: 0.8 }) as ArticleSummary

function setup(props: Partial<React.ComponentProps<typeof ArticleRowsList>> = {}) {
  render(
    <MemoryRouter>
      <ArticleRowsList articles={[]} total={0} {...props} />
    </MemoryRouter>
  )
}

describe("ArticleRowsList", () => {
  it("lista artículos con enlace al reporte, fecha y sentimiento", () => {
    setup({ articles: [article(7, "Una nota")], total: 1 })
    expect(screen.getByRole("link", { name: "Una nota" })).toHaveAttribute("href", "/reports/7")
    expect(screen.getByText("Positivo")).toBeInTheDocument()
    expect(screen.getByText(/2026|mar/i)).toBeInTheDocument()
  })

  it("muestra esqueleto mientras carga", () => {
    setup({ loading: true })
    expect(screen.getByRole("status", { name: /cargando/i })).toBeInTheDocument()
  })

  it("muestra mensaje vacío", () => {
    setup()
    expect(screen.getByText(/no hay artículos/i)).toBeInTheDocument()
  })

  it("muestra un Alert si falla", () => {
    setup({ error: true })
    expect(screen.getByRole("alert")).toBeInTheDocument()
  })

  it("ofrece Cargar más solo si total supera lo mostrado", async () => {
    const onLoadMore = vi.fn()
    const user = userEvent.setup()
    setup({ articles: [article(1, "A")], total: 12, onLoadMore })
    await user.click(screen.getByRole("button", { name: /cargar más/i }))
    expect(onLoadMore).toHaveBeenCalled()
  })

  it("sin más resultados no hay Cargar más", () => {
    setup({ articles: [article(1, "A")], total: 1, onLoadMore: vi.fn() })
    expect(screen.queryByRole("button", { name: /cargar más/i })).not.toBeInTheDocument()
  })
})
