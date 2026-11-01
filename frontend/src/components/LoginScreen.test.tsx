import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { LoginScreen } from "@/components/LoginScreen"
import * as odinApi from "@/lib/odin-api"

vi.mock("@/lib/odin-api", async () => {
  const actual = await vi.importActual<typeof odinApi>("@/lib/odin-api")
  return { ...actual, login: vi.fn() }
})

beforeEach(() => vi.mocked(odinApi.login).mockReset())

describe("LoginScreen", () => {
  it("no dibuja canvas de fondo", () => {
    const { container } = render(<LoginScreen onSuccess={vi.fn()} />)
    expect(container.querySelector("canvas")).toBeNull()
  })

  it("el formulario vive en una tarjeta centrada bajo el título Odin", () => {
    const { container } = render(<LoginScreen onSuccess={vi.fn()} />)
    expect(screen.getByRole("heading", { name: "Odin" })).toBeInTheDocument()
    const card = container.querySelector("[data-slot=card]")
    expect(card).not.toBeNull()
    expect(card).toContainElement(screen.getByLabelText("Usuario"))
  })

  it("los campos tienen etiquetas asociadas", () => {
    render(<LoginScreen onSuccess={vi.fn()} />)
    expect(screen.getByLabelText("Usuario")).toBeInTheDocument()
    expect(screen.getByLabelText("Contraseña")).toBeInTheDocument()
  })

  it("un acceso fallido se anuncia como alerta", async () => {
    vi.mocked(odinApi.login).mockRejectedValueOnce(new odinApi.OdinApiError("Credenciales inválidas"))
    const user = userEvent.setup()
    render(<LoginScreen onSuccess={vi.fn()} />)
    await user.type(screen.getByLabelText("Usuario"), "ana")
    await user.type(screen.getByLabelText("Contraseña"), "mala{Enter}")
    expect(await screen.findByRole("alert")).toHaveTextContent(/credenciales inválidas/i)
  })
})
