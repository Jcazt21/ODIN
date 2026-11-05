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

  it("muestra el título de acceso y el formulario junto a la imagen", () => {
    const { container } = render(<LoginScreen onSuccess={vi.fn()} />)
    expect(screen.getByRole("heading", { name: "Iniciar sesión" })).toBeInTheDocument()
    expect(container.querySelector("aside img")).not.toBeNull()
    expect(screen.getByLabelText("Usuario")).toBeInTheDocument()
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
