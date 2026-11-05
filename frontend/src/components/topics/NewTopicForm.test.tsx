import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { NewTopicForm } from "@/components/topics/NewTopicForm"
import * as odinApi from "@/lib/odin-api"
import type { TopicRow } from "@/lib/topic-tree"

vi.mock("@/lib/odin-api", async () => {
  const actual = await vi.importActual<typeof odinApi>("@/lib/odin-api")
  return { ...actual, createTopic: vi.fn() }
})
const createTopic = vi.mocked(odinApi.createTopic)

const row = (id: number, name: string, depth: number, is_active = true): TopicRow => ({
  id, name, depth, article_count: 0, parent_id: null, is_active,
  description: null, display_order: 0, child_count: 0, has_children: false,
})
const TOPICS = [row(1, "Economía", 0), row(2, "Educación", 1), row(3, "Viejo", 0, false)]

function setup(topics: TopicRow[] = TOPICS) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <NewTopicForm topics={topics} />
    </QueryClientProvider>
  )
  return userEvent.setup()
}

async function openForm(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: "Nuevo tema" }))
}

beforeEach(() => {
  createTopic.mockReset()
  createTopic.mockResolvedValue({} as never)
})

describe("NewTopicForm", () => {
  it("no envía con nombre vacío", async () => {
    const user = setup()
    expect(screen.queryByLabelText("Nombre")).not.toBeInTheDocument()
    await openForm(user)
    await user.type(screen.getByLabelText("Nombre"), "   ")
    await user.click(screen.getByRole("button", { name: "Crear tema" }))
    expect(screen.getByText("El nombre es obligatorio")).toBeInTheDocument()
    expect(createTopic).not.toHaveBeenCalled()
  })

  it("envía payload sin slug y sin padre", async () => {
    const user = setup()
    await openForm(user)
    await user.type(screen.getByLabelText("Nombre"), " Salud ")
    await user.type(screen.getByLabelText("Descripción"), "Sistema sanitario")
    await user.click(screen.getByRole("button", { name: "Crear tema" }))
    await waitFor(() => expect(createTopic).toHaveBeenCalledTimes(1))
    expect(createTopic.mock.calls[0][0]).toEqual({
      name: "Salud", description: "Sistema sanitario", parent_id: null,
    })
  })

  it("envía parent_id al elegir padre", async () => {
    const user = setup()
    await openForm(user)
    await user.type(screen.getByLabelText("Nombre"), "Subtema")
    await user.selectOptions(screen.getByLabelText("Tema padre"), "1")
    await user.click(screen.getByRole("button", { name: "Crear tema" }))
    await waitFor(() => expect(createTopic).toHaveBeenCalled())
    expect(createTopic.mock.calls[0][0]).toMatchObject({ name: "Subtema", parent_id: 1 })
  })

  it("no lista temas inactivos como padre y sangra por depth", async () => {
    const user = setup()
    await openForm(user)
    const options = within(screen.getByLabelText("Tema padre")).getAllByRole("option")
    expect(options.map((o) => o.textContent?.replace(/ /g, " ").trim())).toEqual([
      "Sin padre (raíz)", "Economía", "Educación",
    ])
    expect(options[2].textContent).toMatch(/^ +Educación$/)
  })

  it("limpia y cierra al éxito", async () => {
    const user = setup()
    await openForm(user)
    await user.type(screen.getByLabelText("Nombre"), "Salud")
    await user.click(screen.getByRole("button", { name: "Crear tema" }))
    await waitFor(() => expect(screen.queryByLabelText("Nombre")).not.toBeInTheDocument())
    await openForm(user)
    expect(screen.getByLabelText("Nombre")).toHaveValue("")
  })

  it("muestra el mensaje 409 y deja el formulario abierto", async () => {
    createTopic.mockRejectedValue(new odinApi.OdinApiError("'Salud' ya existe bajo ese tema padre."))
    const user = setup()
    await openForm(user)
    await user.type(screen.getByLabelText("Nombre"), "Salud")
    await user.click(screen.getByRole("button", { name: "Crear tema" }))
    expect(await screen.findByText("'Salud' ya existe bajo ese tema padre.")).toBeInTheDocument()
    expect(screen.getByLabelText("Nombre")).toHaveValue("Salud")
  })

  it("deshabilita el botón mientras envía", async () => {
    createTopic.mockReturnValue(new Promise(() => {}))
    const user = setup()
    await openForm(user)
    await user.type(screen.getByLabelText("Nombre"), "Salud")
    await user.click(screen.getByRole("button", { name: "Crear tema" }))
    expect(await screen.findByRole("button", { name: "Creando…" })).toBeDisabled()
  })
})
