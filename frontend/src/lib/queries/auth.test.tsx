import { describe, expect, it, vi, beforeEach } from "vitest"
import { renderHook, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { useMe } from "@/lib/queries/auth"
import { setSession, clearSession } from "@/lib/auth"
import * as odinApi from "@/lib/odin-api"

vi.mock("@/lib/odin-api", async () => {
  const actual = await vi.importActual<typeof odinApi>("@/lib/odin-api")
  return { ...actual, getMe: vi.fn() }
})

const mockedMe = vi.mocked(odinApi.getMe)

describe("useMe — identidad de la sesión", () => {
  beforeEach(() => {
    mockedMe.mockReset()
    clearSession()
  })

  it("no sirve el `me` de la sesión anterior a la siguiente", async () => {
    /* El fallo que esto atrapa: como es una SPA, cerrar sesión no recarga la
       página, así que la caché en memoria sobrevive. Con una clave constante y
       staleTime infinito, quien entraba después recibía el `me` del usuario
       anterior — y si ese traía must_change_password en false, la pantalla de
       cambio obligatorio nunca aparecía, mientras el backend ya había
       consumido el PIN de un solo uso. */
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    )

    setSession("token-del-admin", "jazar")
    mockedMe.mockResolvedValue({
      username: "jazar",
      role: "admin",
      must_change_password: false,
    } as never)
    const first = renderHook(() => useMe(), { wrapper })
    await waitFor(() => expect(first.result.current.data?.username).toBe("jazar"))

    // Cierra sesión y entra otra persona, sin recargar la página.
    clearSession()
    setSession("token-del-nuevo", "mgomez")
    mockedMe.mockResolvedValue({
      username: "mgomez",
      role: "documentalista",
      must_change_password: true,
    } as never)
    const second = renderHook(() => useMe(), { wrapper })

    await waitFor(() => expect(second.result.current.data?.username).toBe("mgomez"))
    expect(second.result.current.data?.must_change_password).toBe(true)
  })
})
