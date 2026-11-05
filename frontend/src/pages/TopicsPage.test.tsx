import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { DialogProvider } from "@/lib/dialog"
import { TopicsPage } from "@/pages/TopicsPage"
import * as topicQueries from "@/lib/queries/topics"

vi.mock("@/lib/queries/topics")

const node = (
  id: number, name: string, article_count: number, children: unknown[] = [], over: Record<string, unknown> = {},
) => ({
  id, name, slug: `t${id}`, parent_id: null, aliases: [], article_count, children,
  is_active: true, description: null, display_order: 0, child_count: children.length, ...over,
})
const TREE = [node(1, "Economía", 5, [node(2, "Educación pública", 2)]), node(3, "Deportes", 0)]

function mockTree(partial: Record<string, unknown> = {}) {
  vi.mocked(topicQueries.useTopicTree).mockReturnValue({
    data: TREE, isLoading: false, error: null, ...partial,
  } as never)
}

function ui() {
  return (
    <MemoryRouter>
      <DialogProvider>
        <TopicsPage />
      </DialogProvider>
    </MemoryRouter>
  )
}

function renderPage() {
  render(ui())
  return userEvent.setup()
}

const idleMutation = { mutate: vi.fn(), mutateAsync: vi.fn(), reset: vi.fn(), isPending: false, error: null }

beforeEach(() => {
  vi.mocked(topicQueries.useCreateTopic).mockReturnValue(idleMutation as never)
  vi.mocked(topicQueries.useUpdateTopic).mockReturnValue(idleMutation as never)
  vi.mocked(topicQueries.useDeleteTopic).mockReturnValue(idleMutation as never)
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
    await user.click(screen.getByRole("button", { name: "Ver artículos de Economía" }))
    expect(topicQueries.useTopicArticles).toHaveBeenCalledWith(1, true, expect.anything())
    expect(screen.getByRole("link", { name: "Nota económica" })).toHaveAttribute("href", "/reports/9")
  })

  it("estados", () => {
    mockTree({ data: undefined, isLoading: true })
    const a = render(ui())
    expect(screen.getByRole("status", { name: /cargando temas/i })).toBeInTheDocument()
    a.unmount()
    mockTree({ data: [] })
    const b = render(ui())
    expect(screen.getByText(/no hay temas/i)).toBeInTheDocument()
    b.unmount()
    mockTree({ data: undefined, error: new Error("x") })
    render(ui())
    expect(screen.getByRole("alert")).toBeInTheDocument()
  })

  it("muestra el formulario de alta", async () => {
    const user = renderPage()
    expect(screen.queryByLabelText("Nombre")).not.toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Nuevo tema" }))
    expect(screen.getByLabelText("Nombre")).toBeInTheDocument()
  })

  it("renderiza las 4 columnas", () => {
    renderPage()
    const headers = screen.getAllByRole("columnheader").map((h) => h.textContent)
    expect(headers).toEqual(["Expandir", "Tema", "Artículos", "Estado", "Acciones"])
    const row = screen.getByText("Deportes").closest("tr")!
    expect(within(row).getByRole("switch", { name: "Desactivar tema Deportes" })).toBeInTheDocument()
    expect(within(row).getByRole("button", { name: "Editar tema Deportes" })).toBeInTheDocument()
  })

  it("un tema inactivo se ve atenuado con Incluir inactivos", () => {
    mockTree({ data: [node(1, "Economía", 0, [], { is_active: false })] })
    renderPage()
    const row = screen.getByText("Economía").closest("tr")!
    expect(within(row).getByRole("switch", { name: "Activar tema Economía" })).toBeInTheDocument()
    expect(screen.getByText("Economía").closest("td")!.className).toContain("opacity-45")
  })

  it("muestra CTA cuando no hay temas y abre el formulario", async () => {
    mockTree({ data: [] })
    const user = renderPage()
    await user.click(screen.getByRole("button", { name: "Crea el primer tema" }))
    expect(screen.getByLabelText("Nombre")).toBeInTheDocument()
  })

  it("no muestra CTA al buscar sin resultados", async () => {
    const user = renderPage()
    await user.type(screen.getByLabelText("Buscar temas"), "zzzz")
    expect(screen.getByText("No hay temas que coincidan.")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Crea el primer tema" })).not.toBeInTheDocument()
  })
})
