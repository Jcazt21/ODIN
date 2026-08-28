import { describe, expect, it, vi, beforeEach } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { MemoryRouter } from "react-router-dom"
import { AnalyzePage } from "@/pages/AnalyzePage"
import * as odinApi from "@/lib/odin-api"

vi.mock("@/lib/odin-api", async () => {
  const actual = await vi.importActual<typeof odinApi>("@/lib/odin-api")
  return {
    ...actual,
    analyzeUrl: vi.fn(),
    saveArticle: vi.fn(),
    getLocalityTree: vi.fn(),
  }
})

const mockedAnalyze = vi.mocked(odinApi.analyzeUrl)
const mockedSave = vi.mocked(odinApi.saveArticle)
const mockedTree = vi.mocked(odinApi.getLocalityTree)

const DRAFT = {
  already_saved: false,
  source: "listin_diario",
  url: "https://listindiario.com/nota",
  title: "Las Charcas lleva dos meses sin agua",
  body: "cuerpo",
  main_topic: "agua potable",
  entities: [],
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AnalyzePage />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

async function analyze(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByRole("textbox"), "https://listindiario.com/nota")
  await user.click(screen.getByRole("button", { name: /^analizar$/i }))
  await screen.findByText(DRAFT.title as string)
}

describe("AnalyzePage — lugar de la noticia en la vista previa", () => {
  beforeEach(() => {
    mockedAnalyze.mockReset()
    mockedSave.mockReset()
    mockedTree.mockReset()
    mockedAnalyze.mockResolvedValue(DRAFT as never)
    mockedSave.mockResolvedValue({ ...DRAFT, id: 9 } as never)
    mockedTree.mockResolvedValue([
      {
        id: 1,
        name: "República Dominicana",
        level: "PAIS",
        aliases: [],
        children: [],
      },
    ] as unknown as Awaited<ReturnType<typeof odinApi.getLocalityTree>>)
  })

  it("ofrece indicar el lugar antes de guardar", async () => {
    const user = userEvent.setup()
    renderPage()

    await analyze(user)

    expect(screen.getByText(/lugar de la noticia/i)).toBeTruthy()
  })

  it("manda los lugares en el mismo guardado", async () => {
    /* En el mismo POST y no en una segunda llamada: así el reporte y sus
       lugares entran juntos o no entra ninguno. */
    const user = userEvent.setup()
    renderPage()
    await analyze(user)

    await user.click(screen.getByRole("button", { name: /agregar/i }))
    await user.click(screen.getAllByRole("button", { name: /guardar reporte/i })[0])

    await waitFor(() => expect(mockedSave).toHaveBeenCalled())
    const payload = mockedSave.mock.calls[0][0] as Record<string, unknown>
    expect(Array.isArray(payload.localities)).toBe(true)
  })

  it("guarda sin lugares si no se indica ninguno", async () => {
    const user = userEvent.setup()
    renderPage()
    await analyze(user)

    await user.click(screen.getAllByRole("button", { name: /guardar reporte/i })[0])

    await waitFor(() => expect(mockedSave).toHaveBeenCalled())
    expect((mockedSave.mock.calls[0][0] as Record<string, unknown>).localities).toEqual([])
  })
})
