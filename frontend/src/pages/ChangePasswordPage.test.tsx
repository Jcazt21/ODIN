import { describe, expect, it, vi, beforeEach } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { ChangePasswordPage } from "@/pages/ChangePasswordPage"
import * as odinApi from "@/lib/odin-api"

vi.mock("@/lib/odin-api", async () => {
  const actual = await vi.importActual<typeof odinApi>("@/lib/odin-api")
  return { ...actual, changePassword: vi.fn() }
})

const mockedChange = vi.mocked(odinApi.changePassword)

function renderPage(onDone = vi.fn()) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <ChangePasswordPage onDone={onDone} />
    </QueryClientProvider>
  )
  return onDone
}

describe("ChangePasswordPage", () => {
  beforeEach(() => {
    mockedChange.mockReset()
    mockedChange.mockResolvedValue({
      access_token: "nuevo",
      expires_in: 3600,
      username: "nuevo",
    } as unknown as odinApi.LoginResponse)
  })

  it("rechaza una contraseña de menos de 8 sin llamar a la API", async () => {
    const user = userEvent.setup()
    renderPage()

    await user.type(screen.getByLabelText(/nueva contraseña/i), "corta12")
    await user.type(screen.getByLabelText(/repet/i), "corta12")
    await user.click(screen.getByRole("button", { name: /cambiar/i }))

    // Por rol: el texto explicativo de arriba también menciona el mínimo.
    expect((await screen.findByRole("alert")).textContent).toMatch(/al menos 8/i)
    expect(mockedChange).not.toHaveBeenCalled()
  })

  it("exige que las dos escrituras coincidan", async () => {
    const user = userEvent.setup()
    renderPage()

    await user.type(screen.getByLabelText(/nueva contraseña/i), "una-clave-decente")
    await user.type(screen.getByLabelText(/repet/i), "otra-clave-distinta")
    await user.click(screen.getByRole("button", { name: /cambiar/i }))

    expect((await screen.findByRole("alert")).textContent).toMatch(/no coinciden/i)
    expect(mockedChange).not.toHaveBeenCalled()
  })

  it("cambia la contraseña y avisa que terminó", async () => {
    const user = userEvent.setup()
    const onDone = renderPage()

    await user.type(screen.getByLabelText(/nueva contraseña/i), "una-clave-decente")
    await user.type(screen.getByLabelText(/repet/i), "una-clave-decente")
    await user.click(screen.getByRole("button", { name: /cambiar/i }))

    await waitFor(() => expect(mockedChange).toHaveBeenCalledWith("una-clave-decente"))
    await waitFor(() => expect(onDone).toHaveBeenCalled())
  })

  it("no ofrece salida: no hay cerrar ni cancelar", () => {
    renderPage()

    expect(screen.queryByRole("button", { name: /cancelar|cerrar|omitir|después/i })).toBeNull()
  })
})
