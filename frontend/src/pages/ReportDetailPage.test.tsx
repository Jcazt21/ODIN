import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { DialogProvider } from "@/lib/dialog"
import { ReportDetailPage } from "@/pages/ReportDetailPage"
import * as articlesQueries from "@/lib/queries/articles"

vi.mock("@/lib/queries/articles")
vi.mock("@/components/LocalitiesCard", () => ({ LocalitiesCard: () => null }))

const ARTICLE = {
  id: 7,
  source: "acento",
  url: "https://acento.com.do/nota",
  title: "Apagones desde temprano",
  body: "cuerpo",
  entities: [],
  authors: null,
  section: null,
  published_at: null,
}
const deleteMutateAsync = vi.fn()

function renderPage() {
  render(
    <DialogProvider>
      <MemoryRouter initialEntries={["/reports/7"]}>
        <Routes>
          <Route path="/reports/:id" element={<ReportDetailPage />} />
          <Route path="/reports" element={<p>Lista de reportes</p>} />
        </Routes>
      </MemoryRouter>
    </DialogProvider>
  )
  return userEvent.setup()
}

beforeEach(() => {
  deleteMutateAsync.mockReset().mockResolvedValue(undefined)
  vi.mocked(articlesQueries.useArticle).mockReturnValue({ data: ARTICLE, isLoading: false, error: null } as never)
  vi.mocked(articlesQueries.useUpdateArticle).mockReturnValue({ mutateAsync: vi.fn(), reset: vi.fn(), isPending: false, error: null } as never)
  vi.mocked(articlesQueries.useDeleteArticle).mockReturnValue({ mutateAsync: deleteMutateAsync, isPending: false, error: null } as never)
})

describe("ReportDetailPage", () => {
  it("«Volver a reportes» es un link", () => {
    renderPage()
    expect(screen.getByRole("link", { name: /volver a reportes/i })).toHaveAttribute("href", "/reports")
  })

  it("agrupa Editar y Eliminar", () => {
    renderPage()
    const group = screen.getByRole("group", { name: /acciones del reporte/i })
    expect(within(group).getByRole("button", { name: /editar/i })).toBeInTheDocument()
    expect(within(group).getByRole("button", { name: /eliminar/i })).toBeInTheDocument()
  })

  it("eliminar pide confirmación y solo borra si se acepta", async () => {
    const user = renderPage()
    await user.click(screen.getByRole("button", { name: /^eliminar$/i }))
    await user.click(await screen.findByRole("button", { name: "Cancelar" }))
    expect(deleteMutateAsync).not.toHaveBeenCalled()

    await user.click(screen.getByRole("button", { name: /^eliminar$/i }))
    const dialog = await screen.findByRole("dialog")
    await user.click(within(dialog).getByRole("button", { name: "Eliminar" }))
    expect(deleteMutateAsync).toHaveBeenCalledWith(7)
    expect(await screen.findByText("Lista de reportes")).toBeInTheDocument()
  })

  it("tiene un encabezado de página", () => {
    renderPage()
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument()
  })

  it("h1 visible (no sr-only)", () => {
    renderPage()
    expect(screen.getByRole("heading", { level: 1 })).not.toHaveClass("sr-only")
  })
})
