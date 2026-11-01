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

describe("AnalyzePage — formulario de enlace", () => {
  beforeEach(() => {
    mockedAnalyze.mockReset()
    mockedAnalyze.mockResolvedValue(DRAFT as never)
    mockedTree.mockReset()
    mockedTree.mockResolvedValue([] as never)
  })

  const field = () => screen.getByRole("textbox", { name: /enlace|url/i })

  it("enfoca el campo al montar y no expone la ruta técnica", () => {
    renderPage()
    expect(field()).toHaveFocus()
    expect(screen.queryByText(/POST \/api\/analyze/)).not.toBeInTheDocument()
  })

  it("Enter analiza la URL sin espacios", async () => {
    const user = userEvent.setup()
    renderPage()
    await user.type(field(), "  https://listindiario.com/nota  {Enter}")
    await waitFor(() => expect(mockedAnalyze).toHaveBeenCalled())
    expect(mockedAnalyze.mock.calls[0][0]).toBe("https://listindiario.com/nota")
  })

  it("un valor que no es URL no analiza y explica el error junto al campo", async () => {
    const user = userEvent.setup()
    renderPage()
    await user.type(field(), "hola{Enter}")
    expect(mockedAnalyze).not.toHaveBeenCalled()
    const describedBy = field().getAttribute("aria-describedby")
    expect(describedBy).toBeTruthy()
    expect(document.getElementById(describedBy!)).toHaveTextContent(/enlace válido/i)
  })

  it("un campo vacío tampoco analiza", async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(screen.getByRole("button", { name: /^analizar$/i }))
    expect(mockedAnalyze).not.toHaveBeenCalled()
    expect(field()).toHaveAttribute("aria-invalid", "true")
  })
})

describe("AnalyzePage — progreso y error", () => {
  beforeEach(() => {
    mockedAnalyze.mockReset()
    mockedTree.mockReset()
    mockedTree.mockResolvedValue([] as never)
  })

  it("mientras analiza deshabilita el formulario y anuncia la etapa", async () => {
    mockedAnalyze.mockImplementation(((_url: string, onStatus?: (s: string, st: string | null) => void) => {
      onStatus?.("running", "analyzing")
      return new Promise(() => {})
    }) as never)
    const user = userEvent.setup()
    renderPage()
    await user.type(screen.getByRole("textbox", { name: /enlace/i }), "https://listindiario.com/nota{Enter}")

    const status = await screen.findByRole("status")
    await waitFor(() => expect(status).toHaveTextContent(/analizando con el modelo/i))
    expect(screen.getByRole("textbox", { name: /enlace/i })).toBeDisabled()
    expect(screen.getByRole("button", { name: /analizando/i })).toBeDisabled()
  })

  it("ante un error ofrece Reintentar con la misma URL", async () => {
    mockedAnalyze.mockRejectedValueOnce(new Error("boom")).mockResolvedValueOnce(DRAFT as never)
    const user = userEvent.setup()
    renderPage()
    await user.type(screen.getByRole("textbox", { name: /enlace/i }), "https://listindiario.com/nota{Enter}")

    const alert = await screen.findByRole("alert")
    expect(alert).toHaveTextContent(/no se pudo/i)
    await user.click(screen.getByRole("button", { name: /reintentar/i }))

    await screen.findByText(DRAFT.title)
    expect(mockedAnalyze).toHaveBeenCalledTimes(2)
    expect(mockedAnalyze.mock.calls[1][0]).toBe("https://listindiario.com/nota")
  })
})

describe("AnalyzePage — barra de acción y siguiente paso", () => {
  beforeEach(() => {
    mockedAnalyze.mockReset()
    mockedSave.mockReset()
    mockedTree.mockReset()
    mockedTree.mockResolvedValue([] as never)
    mockedAnalyze.mockResolvedValue(DRAFT as never)
    mockedSave.mockResolvedValue({ ...DRAFT, id: 9 } as never)
  })

  it("en borrador hay un solo Guardar reporte y un solo Descartar", async () => {
    const user = userEvent.setup()
    renderPage()
    await analyze(user)
    expect(screen.getByRole("button", { name: /guardar reporte/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /descartar/i })).toBeInTheDocument()
    expect(screen.getByText(/vista previa · sin guardar/i)).toBeInTheDocument()
  })

  it("tras guardar ofrece Ver reporte y Analizar otro, que limpia y enfoca el campo", async () => {
    const user = userEvent.setup()
    renderPage()
    await analyze(user)
    await user.click(screen.getByRole("button", { name: /guardar reporte/i }))

    const link = await screen.findByRole("link", { name: /ver reporte/i })
    expect(link).toHaveAttribute("href", "/reports/9")

    await user.click(screen.getByRole("button", { name: /analizar otro/i }))
    expect(screen.queryByText(DRAFT.title)).not.toBeInTheDocument()
    expect(screen.getByRole("textbox", { name: /enlace/i })).toHaveFocus()
  })

  it("un artículo ya guardado ofrece Ver reporte", async () => {
    mockedAnalyze.mockResolvedValue({ ...DRAFT, already_saved: true, id: 5 } as never)
    const user = userEvent.setup()
    renderPage()
    await analyze(user)
    expect(screen.getByRole("link", { name: /ver reporte/i })).toHaveAttribute("href", "/reports/5")
  })

  it("usa PageHeader (h1 Analizar)", () => {
    renderPage()
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1)
    expect(screen.getByRole("heading", { level: 1, name: /^Analizar/ })).toBeInTheDocument()
  })
})
