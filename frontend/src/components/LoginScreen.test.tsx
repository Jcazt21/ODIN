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

  it("el título del formulario es Iniciar sesión y la marca Odin acompaña a la pintura", () => {
    const { container } = render(<LoginScreen onSuccess={vi.fn()} />)
    expect(screen.getByRole("heading", { name: "Iniciar sesión" })).toBeInTheDocument()
    expect(screen.getAllByText("Odin").length).toBeGreaterThan(0)
    expect(screen.getByText(/monitoreo y análisis de prensa dominicana/i)).toBeInTheDocument()
    // La pintura es decorativa: sin texto alternativo para lectores de pantalla.
    expect(container.querySelector("img")).toHaveAttribute("aria-hidden", "true")
  })

  it("indica que las cuentas las gestiona un administrador", () => {
    render(<LoginScreen onSuccess={vi.fn()} />)
    expect(screen.getByText(/pídele a un administrador/i)).toBeInTheDocument()
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
