import { describe, expect, it, vi, beforeEach } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { MemoryRouter } from "react-router-dom"
import { NewReportPage } from "@/pages/NewReportPage"
import * as odinApi from "@/lib/odin-api"

const navigate = vi.fn()
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom")
  return { ...actual, useNavigate: () => navigate }
})

vi.mock("@/lib/odin-api", async () => {
  const actual = await vi.importActual<typeof odinApi>("@/lib/odin-api")
  return {
    ...actual,
    listSources: vi.fn(),
    getArticleFilterOptions: vi.fn(),
    getLocalityTree: vi.fn(),
    createArticle: vi.fn(),
  }
})

const mockedSources = vi.mocked(odinApi.listSources)
const mockedFacets = vi.mocked(odinApi.getArticleFilterOptions)
const mockedTree = vi.mocked(odinApi.getLocalityTree)
const mockedCreate = vi.mocked(odinApi.createArticle)

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <NewReportPage />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

async function fillRequired(user: ReturnType<typeof userEvent.setup>) {
  await user.selectOptions(screen.getByLabelText(/medio/i), "listin_diario")
  await user.type(screen.getByLabelText(/url/i), "https://listindiario.com/nota")
  await user.type(screen.getByLabelText(/título/i), "Un título")
  await user.type(screen.getByLabelText(/cuerpo/i), "El cuerpo de la nota.")
}

describe("NewReportPage", () => {
  beforeEach(() => {
    navigate.mockReset()
    mockedSources.mockReset()
    mockedFacets.mockReset()
    mockedTree.mockReset()
    mockedCreate.mockReset()

    mockedSources.mockResolvedValue([
      { value: "listin_diario", label: "Listín Diario" },
      { value: "diario_libre", label: "Diario Libre" },
    ])
    mockedFacets.mockResolvedValue({
      sources: [],
      topics: ["agua potable", "energía"],
      sections: [],
      sentiments: [],
      framing: [],
      headline_intent: [],
      lead_orientation: [],
      source_quality: [],
      documentalists: [],
    } as unknown as odinApi.ArticleFilterOptions)
    mockedTree.mockResolvedValue([])
    mockedCreate.mockResolvedValue({
      article: { id: 7, title: "Un título" } as unknown as odinApi.ArticleAnalysis,
      alreadyExisted: false,
    })
  })

  it("ofrece los medios del registro por su nombre legible", async () => {
    renderPage()

    expect(await screen.findByRole("option", { name: "Listín Diario" })).toBeTruthy()
    expect(screen.getByRole("option", { name: "Diario Libre" })).toBeTruthy()
  })

  it("sugiere los temas ya usados sin impedir uno nuevo", async () => {
    renderPage()

    const tema = (await screen.findByLabelText(/tema/i)) as HTMLInputElement
    await waitFor(() => {
      const datalist = document.getElementById(tema.getAttribute("list") ?? "")
      expect(datalist?.querySelectorAll("option").length).toBe(2)
    })
    expect(tema.getAttribute("readonly")).toBeNull()
  })

  it("no envía si falta un campo obligatorio", async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole("button", { name: /guardar/i }))

    expect(mockedCreate).not.toHaveBeenCalled()
  })

  it("guarda y navega al detalle del reporte nuevo", async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole("option", { name: "Listín Diario" })

    await fillRequired(user)
    await user.click(screen.getByRole("button", { name: /guardar/i }))

    await waitFor(() => expect(mockedCreate).toHaveBeenCalledTimes(1))
    expect(mockedCreate.mock.calls[0][0]).toMatchObject({
      source: "listin_diario",
      url: "https://listindiario.com/nota",
      title: "Un título",
      localities: [],
    })
    await waitFor(() => expect(navigate).toHaveBeenCalledWith("/reports/7"))
  })

  it("avisa en vez de fingir éxito cuando la URL ya estaba cargada", async () => {
    mockedCreate.mockResolvedValue({
      article: { id: 3, title: "La que ya estaba" } as unknown as odinApi.ArticleAnalysis,
      alreadyExisted: true,
    })
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole("option", { name: "Listín Diario" })

    await fillRequired(user)
    await user.click(screen.getByRole("button", { name: /guardar/i }))

    expect(await screen.findByText(/ya (está|estaba) cargada/i)).toBeTruthy()
    expect(navigate).not.toHaveBeenCalled()
    // Lo escrito no se pierde: el documentalista decide qué hacer.
    expect((screen.getByLabelText(/título/i) as HTMLInputElement).value).toBe("Un título")
  })
})
