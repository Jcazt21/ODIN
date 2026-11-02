import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { MemoryRouter } from "react-router-dom"
import { AuthorsPage } from "@/pages/AuthorsPage"
import * as authorQueries from "@/lib/queries/authors"
import * as sourceQueries from "@/lib/queries/sources"

vi.mock("@/lib/queries/authors")
vi.mock("@/lib/queries/sources")

const AUTHORS = [
  { name: "Ana Pérez", article_count: 3, sources: ["listin"], last_published_at: "2026-03-04T12:00:00Z" },
  { name: "Luis Soto", article_count: 1, sources: ["acento", "listin"], last_published_at: null },
]

function mockAuthors(partial: Record<string, unknown> = {}) {
  vi.mocked(authorQueries.useAuthors).mockReturnValue({
    data: { items: AUTHORS, total: AUTHORS.length },
    isLoading: false,
    isPending: false,
    error: null,
    ...partial,
  } as never)
}

function renderPage() {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>
        <AuthorsPage />
      </MemoryRouter>
    </QueryClientProvider>
  )
  return userEvent.setup()
}

const lastParams = () => vi.mocked(authorQueries.useAuthors).mock.calls.at(-1)![0]

beforeEach(() => {
  vi.mocked(sourceQueries.useSources).mockReturnValue({
    data: [{ value: "listin", label: "Listín Diario" }, { value: "acento", label: "Acento" }],
  } as never)
  vi.mocked(authorQueries.useAuthorArticles).mockReturnValue({
    data: { items: [{ id: 5, title: "Nota de Ana", published_at: null, overall_sentiment: "NEU" }], total: 1 },
    isLoading: false,
    isPending: false,
    isError: false,
  } as never)
  mockAuthors()
})

describe("AuthorsPage", () => {
  it("lista autores con conteo", () => {
    renderPage()
    expect(screen.getByRole("heading", { level: 1, name: "Autores" })).toBeInTheDocument()
    expect(screen.getByText("2 autores")).toBeInTheDocument()
    const row = screen.getByText("Ana Pérez").closest("tr")!
    expect(within(row).getByText("3")).toBeInTheDocument()
    expect(within(row).getByText("Listín Diario")).toBeInTheDocument()
  })

  it("búsqueda, fuente y orden pasan a useAuthors", async () => {
    const user = renderPage()
    await user.selectOptions(screen.getByLabelText("Fuente"), "listin")
    await user.selectOptions(screen.getByLabelText("Ordenar por"), "name")
    expect(lastParams()).toMatchObject({ source: "listin", sort: "name" })
    await user.type(screen.getByLabelText("Buscar autores"), "ana")
    await vi.waitFor(() => expect(lastParams()).toMatchObject({ q: "ana" }))
  })

  it("expandir carga los artículos del autor, y solo de ese", async () => {
    const user = renderPage()
    expect(authorQueries.useAuthorArticles).not.toHaveBeenCalled()
    await user.click(screen.getByRole("button", { name: /Ana Pérez/ }))
    expect(authorQueries.useAuthorArticles).toHaveBeenCalledWith("Ana Pérez", true, expect.anything())
    expect(authorQueries.useAuthorArticles).not.toHaveBeenCalledWith("Luis Soto", expect.anything(), expect.anything())
    expect(screen.getByRole("link", { name: "Nota de Ana" })).toHaveAttribute("href", "/reports/5")
    await user.click(screen.getByRole("button", { name: /Ana Pérez/ }))
    expect(screen.queryByRole("link", { name: "Nota de Ana" })).not.toBeInTheDocument()
  })

  it("estados: carga, vacío y error", () => {
    mockAuthors({ data: undefined, isLoading: true, isPending: true })
    const { unmount } = render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <AuthorsPage />
        </MemoryRouter>
      </QueryClientProvider>
    )
    expect(screen.getAllByRole("status", { name: /cargando/i })[0]).toBeInTheDocument()
    unmount()

    mockAuthors({ data: { items: [], total: 0 } })
    const second = render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <AuthorsPage />
        </MemoryRouter>
      </QueryClientProvider>
    )
    expect(screen.getByText(/no hay autores/i)).toBeInTheDocument()
    second.unmount()

    mockAuthors({ data: undefined, error: new Error("falló") })
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <AuthorsPage />
        </MemoryRouter>
      </QueryClientProvider>
    )
    expect(screen.getByRole("alert")).toBeInTheDocument()
  })
})
