import { describe, expect, it, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { SettingsPage } from "@/pages/SettingsPage"
import { setSession, setRole } from "@/lib/auth"
import * as odinApi from "@/lib/odin-api"

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom")
  return { ...actual, useOutletContext: () => ({ theme: "dark", onToggleTheme: vi.fn() }) }
})

vi.mock("@/lib/odin-api", async () => {
  const actual = await vi.importActual<typeof odinApi>("@/lib/odin-api")
  return {
    ...actual,
    listDocumentalists: vi.fn(),
    createDocumentalist: vi.fn(),
    resetDocumentalistPin: vi.fn(),
    getMe: vi.fn(),
  }
})

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <SettingsPage />
    </QueryClientProvider>
  )
}

describe("SettingsPage — alta de usuarios", () => {
  beforeEach(() => {
    localStorage.clear()
    vi.mocked(odinApi.listDocumentalists).mockResolvedValue([] as never)
    vi.mocked(odinApi.getMe).mockResolvedValue({
      username: "jazar",
      role: "admin",
      must_change_password: false,
    } as never)
    setSession("un-token", "jazar")
  })

  it("muestra la tarjeta de usuarios a un admin", async () => {
    setRole("admin")

    renderPage()

    expect(await screen.findByText("Usuarios")).toBeTruthy()
    expect(screen.getByRole("button", { name: /crear usuario/i })).toBeTruthy()
  })

  it("no la muestra a un documentalista", () => {
    setRole("documentalista")

    renderPage()

    expect(screen.queryByText("Usuarios")).toBeNull()
  })

  it("aparece cuando el rol llega, aunque no estuviera en localStorage al montar", async () => {
    /* El fallo que esto atrapa: `setRole` corre en un useEffect de App, o sea
       DESPUÉS del primer render. Leyendo localStorage durante el render, quien
       cargaba la página estando en Ajustes se dibujaba sin rol y no se volvía
       a dibujar al llegar — la tarjeta no aparecía hasta navegar a otro lado y
       volver. El rol tiene que salir de la query, que sí es reactiva. */
    setRole(null)

    renderPage()

    expect(await screen.findByText("Usuarios")).toBeTruthy()
  })

  it("no la muestra a quien no es admin aunque localStorage mienta", async () => {
    setRole("admin")
    vi.mocked(odinApi.getMe).mockResolvedValue({
      username: "pepe",
      role: "documentalista",
      must_change_password: false,
    } as never)

    renderPage()

    await screen.findByText("Tema")
    expect(screen.queryByText("Usuarios")).toBeNull()
  })
})
