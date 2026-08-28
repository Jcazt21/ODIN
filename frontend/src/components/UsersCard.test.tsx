import { describe, expect, it, vi, beforeEach } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { UsersCard } from "@/components/UsersCard"
import * as odinApi from "@/lib/odin-api"

vi.mock("@/lib/odin-api", async () => {
  const actual = await vi.importActual<typeof odinApi>("@/lib/odin-api")
  return {
    ...actual,
    listDocumentalists: vi.fn(),
    createDocumentalist: vi.fn(),
    resetDocumentalistPin: vi.fn(),
  }
})

const mockedList = vi.mocked(odinApi.listDocumentalists)
const mockedCreate = vi.mocked(odinApi.createDocumentalist)
const mockedReset = vi.mocked(odinApi.resetDocumentalistPin)

function renderCard() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <UsersCard />
    </QueryClientProvider>
  )
}

describe("UsersCard", () => {
  beforeEach(() => {
    mockedList.mockReset()
    mockedCreate.mockReset()
    mockedReset.mockReset()
    mockedList.mockResolvedValue([
      {
        id: 1,
        username: "jperez",
        display_name: "Juan Pérez",
        role: "documentalista",
        is_active: true,
        created_at: "2026-08-01T00:00:00Z",
      },
    ] as unknown as Awaited<ReturnType<typeof odinApi.listDocumentalists>>)
    mockedCreate.mockResolvedValue({
      id: 2,
      username: "mgomez",
      display_name: "María Gómez",
      role: "documentalista",
      is_active: true,
      pin: "4071",
    } as unknown as odinApi.DocumentalistCreated)
    mockedReset.mockResolvedValue({
      id: 1,
      username: "jperez",
      display_name: "Juan Pérez",
      role: "documentalista",
      is_active: true,
      pin: "8823",
    } as unknown as odinApi.DocumentalistCreated)
  })

  it("no pide una contraseña: la elige la persona al entrar", async () => {
    renderCard()
    await screen.findByText("Juan Pérez")

    expect(screen.queryByLabelText(/contraseña/i)).toBeNull()
  })

  it("muestra el PIN una sola vez al crear, con el aviso de que no se repite", async () => {
    const user = userEvent.setup()
    renderCard()
    await screen.findByText("Juan Pérez")

    await user.type(screen.getByLabelText(/^nombre$/i), "María")
    await user.type(screen.getByLabelText(/apellido/i), "Gómez")
    await user.click(screen.getByRole("button", { name: /crear/i }))

    expect(await screen.findByText("4071")).toBeTruthy()
    expect(screen.getByText(/no se vuelve a mostrar/i)).toBeTruthy()
  })

  it("manda nombre y apellido por separado, sin usuario", async () => {
    const user = userEvent.setup()
    renderCard()
    await screen.findByText("Juan Pérez")

    await user.type(screen.getByLabelText(/^nombre$/i), "María")
    await user.type(screen.getByLabelText(/apellido/i), "Gómez")
    await user.click(screen.getByRole("button", { name: /crear/i }))

    await waitFor(() => expect(mockedCreate).toHaveBeenCalled())
    const payload = mockedCreate.mock.calls[0][0] as Record<string, unknown>
    expect(payload).toMatchObject({ first_name: "María", last_name: "Gómez" })
    expect(payload.username).toBeUndefined()
  })

  it("adelanta el usuario que se va a generar mientras se escribe", async () => {
    const user = userEvent.setup()
    renderCard()
    await screen.findByText("Juan Pérez")

    await user.type(screen.getByLabelText(/^nombre$/i), "Yván")
    await user.type(screen.getByLabelText(/apellido/i), "Núñez")

    // Sin acentos: es lo que hay que teclear para entrar.
    expect(screen.getByText("ynune")).toBeTruthy()
  })

  it("no envía sin apellido", async () => {
    const user = userEvent.setup()
    renderCard()
    await screen.findByText("Juan Pérez")

    await user.type(screen.getByLabelText(/^nombre$/i), "María")
    await user.click(screen.getByRole("button", { name: /crear/i }))

    expect(mockedCreate).not.toHaveBeenCalled()
  })

  it("regenera el PIN de alguien que quedó afuera", async () => {
    const user = userEvent.setup()
    renderCard()
    await screen.findByText("Juan Pérez")

    await user.click(screen.getByRole("button", { name: /regenerar/i }))

    await waitFor(() => expect(mockedReset).toHaveBeenCalledWith(1))
    expect(await screen.findByText("8823")).toBeTruthy()
  })

  it("no envía sin nombre", async () => {
    const user = userEvent.setup()
    renderCard()
    await screen.findByText("Juan Pérez")

    await user.click(screen.getByRole("button", { name: /crear/i }))

    expect(mockedCreate).not.toHaveBeenCalled()
  })
})
