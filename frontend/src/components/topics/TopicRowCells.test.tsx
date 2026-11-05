import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { TopicRowCells } from "@/components/topics/TopicRowCells"
import { DialogProvider } from "@/lib/dialog"
import * as odinApi from "@/lib/odin-api"
import type { TopicRow } from "@/lib/topic-tree"

vi.mock("@/lib/odin-api", async () => {
  const actual = await vi.importActual<typeof odinApi>("@/lib/odin-api")
  return { ...actual, updateTopic: vi.fn(), deleteTopic: vi.fn() }
})
const updateTopic = vi.mocked(odinApi.updateTopic)
const deleteTopic = vi.mocked(odinApi.deleteTopic)

const TOPIC: TopicRow = {
  id: 7, name: "Salud", depth: 1, article_count: 4, parent_id: 1, is_active: true,
  description: "Sistema sanitario", display_order: 0, child_count: 0, has_children: false,
}

function setup(over: Partial<TopicRow> = {}, onRowClick = vi.fn()) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <DialogProvider>
        <table>
          <tbody>
            <tr onClick={onRowClick}>
              <TopicRowCells topic={{ ...TOPIC, ...over }} />
            </tr>
          </tbody>
        </table>
      </DialogProvider>
    </QueryClientProvider>
  )
  return { user: userEvent.setup(), onRowClick }
}

beforeEach(() => {
  updateTopic.mockReset().mockResolvedValue({} as never)
  deleteTopic.mockReset().mockResolvedValue(undefined)
})

describe("TopicRowCells · vista", () => {
  it("renderiza nombre, descripción y conteo", () => {
    setup()
    const name = screen.getByText("Salud")
    expect(name).toHaveAttribute("data-depth", "1")
    expect(name.style.paddingLeft).toBe("1.25rem")
    expect(screen.getByText("Sistema sanitario")).toBeInTheDocument()
    expect(screen.getByText("4")).toBeInTheDocument()
  })

  it("atenúa solo el texto cuando está inactivo", () => {
    setup({ is_active: false })
    const cells = screen.getAllByRole("cell")
    expect(cells[0].className).toContain("opacity-45")
    expect(cells[1].className).toContain("opacity-45")
    expect(screen.getByRole("switch").closest("td")!.className).not.toContain("opacity-45")
    expect(screen.getByRole("button", { name: "Editar tema Salud" }).closest("td")!.className).not.toContain("opacity-45")
  })
})

describe("TopicRowCells · switch", () => {
  it("envía is_active false al desactivar", async () => {
    const { user } = setup()
    await user.click(screen.getByRole("switch", { name: "Desactivar tema Salud" }))
    await waitFor(() => expect(updateTopic).toHaveBeenCalledWith(7, { is_active: false }))
  })

  it("envía is_active true al reactivar", async () => {
    const { user } = setup({ is_active: false })
    await user.click(screen.getByRole("switch", { name: "Activar tema Salud" }))
    await waitFor(() => expect(updateTopic).toHaveBeenCalledWith(7, { is_active: true }))
  })

  it("el aria-label y aria-checked cambian con el estado", () => {
    setup({ is_active: false })
    const sw = screen.getByRole("switch")
    expect(sw).toHaveAccessibleName("Activar tema Salud")
    expect(sw).toHaveAttribute("aria-checked", "false")
  })
})

describe("TopicRowCells · edición", () => {
  async function startEdit(user: ReturnType<typeof userEvent.setup>) {
    await user.click(screen.getByRole("button", { name: "Editar tema Salud" }))
  }

  it("guardar envía name y description precargados y editados", async () => {
    const { user } = setup()
    await startEdit(user)
    const name = screen.getByLabelText("Nombre del tema")
    expect(name).toHaveValue("Salud")
    expect(screen.getByLabelText("Descripción del tema")).toHaveValue("Sistema sanitario")
    await user.clear(name)
    await user.type(name, " Salud pública ")
    await user.click(screen.getByRole("button", { name: "Guardar" }))
    await waitFor(() =>
      expect(updateTopic).toHaveBeenCalledWith(7, { name: "Salud pública", description: "Sistema sanitario" })
    )
    await waitFor(() => expect(screen.queryByLabelText("Nombre del tema")).not.toBeInTheDocument())
  })

  it("Enter guarda", async () => {
    const { user } = setup()
    await startEdit(user)
    await user.type(screen.getByLabelText("Nombre del tema"), "!{Enter}")
    await waitFor(() => expect(updateTopic).toHaveBeenCalledWith(7, expect.objectContaining({ name: "Salud!" })))
  })

  it("nombre vacío no llama a la API", async () => {
    const { user } = setup()
    await startEdit(user)
    await user.clear(screen.getByLabelText("Nombre del tema"))
    await user.click(screen.getByRole("button", { name: "Guardar" }))
    expect(screen.getByText("El nombre es obligatorio")).toBeInTheDocument()
    expect(updateTopic).not.toHaveBeenCalled()
  })

  it("muestra el error 409 y sigue en edición", async () => {
    updateTopic.mockRejectedValue(new odinApi.OdinApiError("'Salud' ya existe bajo ese tema padre."))
    const { user } = setup()
    await startEdit(user)
    await user.click(screen.getByRole("button", { name: "Guardar" }))
    expect(await screen.findByText("'Salud' ya existe bajo ese tema padre.")).toBeInTheDocument()
    expect(screen.getByLabelText("Nombre del tema")).toBeInTheDocument()
  })

  it("Escape cancela sin llamar a la API", async () => {
    const { user } = setup()
    await startEdit(user)
    await user.type(screen.getByLabelText("Nombre del tema"), "xyz{Escape}")
    expect(screen.queryByLabelText("Nombre del tema")).not.toBeInTheDocument()
    expect(screen.getByText("Salud")).toBeInTheDocument()
    expect(updateTopic).not.toHaveBeenCalled()
  })

  it("el botón de cancelar descarta los cambios", async () => {
    const { user } = setup()
    await startEdit(user)
    await user.type(screen.getByLabelText("Nombre del tema"), "xyz")
    await user.click(screen.getByRole("button", { name: "Cancelar edición" }))
    expect(screen.getByText("Salud")).toBeInTheDocument()
    expect(updateTopic).not.toHaveBeenCalled()
    await startEdit(user)
    expect(screen.getByLabelText("Nombre del tema")).toHaveValue("Salud")
  })
})

describe("TopicRowCells · borrar", () => {
  const dialogText = () => within(screen.getByRole("dialog")).getByText(/se (desactivará|eliminará)/)

  it("confirm de baja lógica si tiene artículos", async () => {
    const { user } = setup({ article_count: 3 })
    await user.click(screen.getByRole("button", { name: "Borrar tema Salud" }))
    expect(dialogText()).toHaveTextContent("se desactivará")
  })

  it("confirm de baja lógica con child_count aunque no haya hijos visibles", async () => {
    const { user } = setup({ article_count: 0, child_count: 2, has_children: false })
    await user.click(screen.getByRole("button", { name: "Borrar tema Salud" }))
    expect(dialogText()).toHaveTextContent("se desactivará")
  })

  it("confirm de borrado definitivo si está vacío", async () => {
    const { user } = setup({ article_count: 0, child_count: 0 })
    await user.click(screen.getByRole("button", { name: "Borrar tema Salud" }))
    expect(dialogText()).toHaveTextContent("se eliminará definitivamente")
  })

  it("cancelar no borra", async () => {
    const { user } = setup()
    await user.click(screen.getByRole("button", { name: "Borrar tema Salud" }))
    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Cancelar" }))
    expect(deleteTopic).not.toHaveBeenCalled()
  })

  it("confirmar borra", async () => {
    const { user } = setup()
    await user.click(screen.getByRole("button", { name: "Borrar tema Salud" }))
    const dialog = screen.getByRole("dialog")
    await user.click(within(dialog).getAllByRole("button").at(-1)!)
    await waitFor(() => expect(deleteTopic).toHaveBeenCalledWith(7))
  })
})

describe("TopicRowCells · propagación", () => {
  it("las acciones no propagan el click", async () => {
    const { user, onRowClick } = setup({ article_count: 1 })
    await user.click(screen.getByRole("switch"))
    await user.click(screen.getByRole("button", { name: "Editar tema Salud" }))
    await user.click(screen.getByRole("button", { name: "Guardar" }))
    await user.click(await screen.findByRole("button", { name: "Editar tema Salud" }))
    await user.click(screen.getByRole("button", { name: "Cancelar edición" }))
    await user.click(screen.getByRole("button", { name: "Borrar tema Salud" }))
    expect(onRowClick).not.toHaveBeenCalled()
  })
})
