import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { TopicsPage } from "@/pages/TopicsPage"
import * as topicQueries from "@/lib/queries/topics"

vi.mock("@/lib/queries/topics")

const node = (id: number, name: string, article_count: number, children: unknown[] = []) => ({
  id, name, slug: `t${id}`, parent_id: null, aliases: [], article_count, children,
})
const TREE = [node(1, "Economía", 5, [node(2, "Educación pública", 2)]), node(3, "Deportes", 0)]

function mockTree(partial: Record<string, unknown> = {}) {
  vi.mocked(topicQueries.useTopicTree).mockReturnValue({
    data: TREE, isLoading: false, error: null, ...partial,
  } as never)
}

function renderPage() {
  render(
    <MemoryRouter>
      <TopicsPage />
    </MemoryRouter>
  )
  return userEvent.setup()
}

beforeEach(() => {
  vi.mocked(topicQueries.useTopicArticles).mockReturnValue({
    data: { items: [{ id: 9, title: "Nota económica", published_at: null, overall_sentiment: "NEG" }], total: 1 },
    isPending: false, isFetching: false, isError: false,
  } as never)
  mockTree()
})

describe("TopicsPage", () => {
  it("lista temas con sangría y conteo", () => {
    renderPage()
    expect(screen.getByRole("heading", { level: 1, name: "Temas" })).toBeInTheDocument()
    expect(screen.getByText("3 temas")).toBeInTheDocument()
    const parent = screen.getByText("Economía").closest("tr")!
    const child = screen.getByText("Educación pública").closest("tr")!
    expect(within(parent).getByText("5")).toBeInTheDocument()
    expect(child.querySelector("[data-depth='1']")).not.toBeNull()
    expect(parent.querySelector("[data-depth='0']")).not.toBeNull()
  })

  it("búsqueda e inactivos", async () => {
    const user = renderPage()
    await user.type(screen.getByLabelText("Buscar temas"), "educacion")
    expect(screen.getByText("Educación pública")).toBeInTheDocument()
    expect(screen.queryByText("Deportes")).not.toBeInTheDocument()
    await user.click(screen.getByLabelText("Incluir inactivos"))
    expect(vi.mocked(topicQueries.useTopicTree).mock.calls.at(-1)![0]).toEqual({ include_inactive: true })
  })

  it("expandir carga artículos del tema", async () => {
    const user = renderPage()
    expect(topicQueries.useTopicArticles).not.toHaveBeenCalled()
    await user.click(screen.getByRole("button", { name: /Economía/ }))
    expect(topicQueries.useTopicArticles).toHaveBeenCalledWith(1, true, expect.anything())
    expect(screen.getByRole("link", { name: "Nota económica" })).toHaveAttribute("href", "/reports/9")
  })

  it("estados", () => {
    mockTree({ data: undefined, isLoading: true })
    const a = render(<MemoryRouter><TopicsPage /></MemoryRouter>)
    expect(screen.getByRole("status", { name: /cargando temas/i })).toBeInTheDocument()
    a.unmount()
    mockTree({ data: [] })
    const b = render(<MemoryRouter><TopicsPage /></MemoryRouter>)
    expect(screen.getByText(/no hay temas/i)).toBeInTheDocument()
    b.unmount()
    mockTree({ data: undefined, error: new Error("x") })
    render(<MemoryRouter><TopicsPage /></MemoryRouter>)
    expect(screen.getByRole("alert")).toBeInTheDocument()
  })
})
