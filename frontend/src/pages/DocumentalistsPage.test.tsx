import { describe, expect, it, vi, beforeEach } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { DocumentalistsPage } from "@/pages/DocumentalistsPage"
import * as odinApi from "@/lib/odin-api"
import { setSession, setRole } from "@/lib/auth"

vi.mock("@/lib/odin-api", async () => {
  const actual = await vi.importActual<typeof odinApi>("@/lib/odin-api")
  return {
    ...actual,
    listDocumentalists: vi.fn(),
    getMe: vi.fn(),
    getDocumentalistKpi: vi.fn(),
  }
})

const mockedList = vi.mocked(odinApi.listDocumentalists)
const mockedKpi = vi.mocked(odinApi.getDocumentalistKpi)

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <DocumentalistsPage />
    </QueryClientProvider>
  )
}

describe("DocumentalistsPage", () => {
  beforeEach(() => {
    setSession("un-token", "jazar")
    setRole("admin")
    vi.mocked(odinApi.getMe).mockResolvedValue({
      username: "jazar",
      role: "admin",
      must_change_password: false,
    } as never)
    mockedList.mockReset()
    mockedKpi.mockReset()
    mockedList.mockResolvedValue([
      {
        id: 1,
        username: "jperez",
        display_name: "Juan Pérez",
        role: "documentalista",
        is_active: true,
        created_at: "2026-08-01T00:00:00Z",
      },
    ] as never)
    mockedKpi.mockResolvedValue([
      {
        documentalist_id: 1,
        display_name: "Juan Pérez",
        articles: 7,
        first_on: "2026-08-18",
        last_on: "2026-08-20",
        active_days: 2,
      },
    ] as never)
  })

  it("lista a los documentalistas", async () => {
    renderPage()

    expect(await screen.findByText("Juan Pérez")).toBeTruthy()
  })

  it("muestra cuántos reportes lleva cada uno", async () => {
    renderPage()

    await waitFor(() => expect(screen.getByText("7")).toBeTruthy())
  })

  it("ya no da de alta: el alta vive en Ajustes con el PIN", async () => {
    /* Un solo lugar para crear usuarios. Dos formularios de alta divergen, y
       el día que uno valide algo que el otro no, el agujero entra por el que
       se olvidó. La cobertura del alta está en UsersCard.test.tsx. */
    renderPage()
    await screen.findByText("Juan Pérez")

    expect(screen.queryByRole("button", { name: /agregar documentalista/i })).toBeNull()
    expect(screen.getByText(/se dan de alta en ajustes/i)).toBeTruthy()
  })

  it("no pide el KPI si el usuario no es admin", async () => {
    setRole("documentalista")
    vi.mocked(odinApi.getMe).mockResolvedValue({
      username: "pepe",
      role: "documentalista",
      must_change_password: false,
    } as never)
    renderPage()
    await screen.findByText("Juan Pérez")

    expect(mockedKpi).not.toHaveBeenCalled()
  })

  it("pide el KPI cuando el rol llega después del montaje", async () => {
    /* Mismo defecto que en Ajustes: `isAdmin()` leía localStorage durante el
       render y `setRole` corre en un useEffect de App, o sea después. Quien
       cargaba la página acá se dibujaba sin rol y el KPI no se pedía nunca. */
    setRole(null)

    renderPage()

    await waitFor(() => expect(mockedKpi).toHaveBeenCalled())
  })
})
