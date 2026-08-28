import { describe, expect, it, vi, beforeEach } from "vitest"
import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { LocalityPicker } from "@/components/LocalityPicker"
import * as odinApi from "@/lib/odin-api"
import type { LocalityNode } from "@/lib/odin-api"

vi.mock("@/lib/odin-api", async () => {
  const actual = await vi.importActual<typeof odinApi>("@/lib/odin-api")
  return { ...actual, getLocalityTree: vi.fn() }
})

const mockedGetTree = vi.mocked(odinApi.getLocalityTree)

/** Árbol con la misma forma que el real: dos macrorregiones, y el nivel REGION
 *  que el formulario NO muestra en medio. Esa capa oculta es justo lo que hace
 *  no trivial acotar Provincia y Municipio. */
const TREE: LocalityNode[] = [
  {
    id: 1,
    name: "República Dominicana",
    level: "PAIS",
    parent_id: null,
    aliases: [],
    children: [
      {
        id: 2,
        name: "Región Norte o Cibao",
        level: "MACRORREGION",
        parent_id: 1,
        aliases: [],
        children: [
          {
            id: 3,
            name: "Cibao Norte",
            level: "REGION",
            parent_id: 2,
            aliases: [],
            children: [
              {
                id: 4,
                name: "Santiago",
                level: "PROVINCIA",
                parent_id: 3,
                aliases: [],
                children: [
                  {
                    id: 5,
                    name: "Tamboril",
                    level: "MUNICIPIO",
                    parent_id: 4,
                    aliases: [],
                    children: [],
                  },
                  {
                    id: 6,
                    name: "Jánico",
                    level: "MUNICIPIO",
                    parent_id: 4,
                    aliases: [],
                    children: [],
                  },
                  {
                    id: 7,
                    name: "Villa Bisonó",
                    level: "MUNICIPIO",
                    parent_id: 4,
                    aliases: ["Navarrete"],
                    children: [],
                  },
                ],
              },
            ],
          },
        ],
      },
      {
        id: 8,
        name: "Región Sur",
        level: "MACRORREGION",
        parent_id: 1,
        aliases: [],
        children: [
          {
            id: 9,
            name: "Valdesia",
            level: "REGION",
            parent_id: 8,
            aliases: [],
            children: [
              {
                id: 10,
                name: "Peravia",
                level: "PROVINCIA",
                parent_id: 9,
                aliases: [],
                children: [
                  {
                    id: 11,
                    name: "Baní",
                    level: "MUNICIPIO",
                    parent_id: 10,
                    aliases: [],
                    children: [],
                  },
                ],
              },
            ],
          },
        ],
      },
    ],
  },
]

function renderPicker(onAdd = vi.fn()) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <LocalityPicker selected={[]} onAdd={onAdd} onRemove={vi.fn()} />
    </QueryClientProvider>
  )
  return onAdd
}

const field = (label: string) => screen.getByLabelText(label) as HTMLInputElement
const listFor = (label: string) => screen.getByRole("listbox", { name: `Opciones de ${label}` })

/** Espera a que el árbol haya llegado: hasta entonces los campos están
 *  deshabilitados y no hay nada que elegir. */
async function ready() {
  await waitFor(() => expect(field("Municipio").disabled).toBe(false))
}

describe("LocalityPicker", () => {
  beforeEach(() => {
    mockedGetTree.mockReset()
    mockedGetTree.mockResolvedValue(TREE)
  })

  it("muestra los cuatro campos del formulario del cliente, vacíos", async () => {
    renderPicker()
    await ready()

    for (const label of ["País", "Región", "Provincia", "Municipio"]) {
      expect(field(label).value).toBe("")
      expect(field(label).placeholder).toBe("Todas")
    }
  })

  describe("cada campo es escribible", () => {
    it("al abrir Municipio sin nada elegido ofrece TODOS los municipios", async () => {
      renderPicker()
      const user = userEvent.setup()
      await ready()

      await user.click(field("Municipio"))

      const list = listFor("Municipio")
      for (const name of ["Tamboril", "Jánico", "Villa Bisonó", "Baní"]) {
        expect(within(list).getByRole("option", { name: new RegExp(name) })).toBeTruthy()
      }
    })

    it("escribir filtra en tiempo real", async () => {
      renderPicker()
      const user = userEvent.setup()
      await ready()

      await user.click(field("Municipio"))
      await user.type(field("Municipio"), "tambo")

      const list = listFor("Municipio")
      expect(within(list).getByRole("option", { name: /Tamboril/ })).toBeTruthy()
      expect(within(list).queryByRole("option", { name: /Jánico/ })).toBeNull()
    })

    it("filtra sin acentos", async () => {
      renderPicker()
      const user = userEvent.setup()
      await ready()

      await user.click(field("Municipio"))
      await user.type(field("Municipio"), "janico")

      expect(within(listFor("Municipio")).getByRole("option", { name: /Jánico/ })).toBeTruthy()
    })

    it("encuentra por alias: 'navarrete' llega a Villa Bisonó", async () => {
      renderPicker()
      const user = userEvent.setup()
      await ready()

      await user.click(field("Municipio"))
      await user.type(field("Municipio"), "navarrete")

      expect(
        within(listFor("Municipio")).getByRole("option", { name: /Villa Bisonó/ })
      ).toBeTruthy()
    })

    it("avisa cuando no hay coincidencias", async () => {
      renderPicker()
      const user = userEvent.setup()
      await ready()

      await user.click(field("Municipio"))
      await user.type(field("Municipio"), "wakanda")

      expect(within(listFor("Municipio")).getByText("Sin resultados")).toBeTruthy()
    })
  })

  describe("elegir rellena los demás campos", () => {
    it("elegir un municipio llena Provincia, Región y País", async () => {
      renderPicker()
      const user = userEvent.setup()
      await ready()

      await user.click(field("Municipio"))
      await user.type(field("Municipio"), "tamboril")
      await user.click(within(listFor("Municipio")).getByRole("option", { name: /Tamboril/ }))

      expect(field("Municipio").value).toBe("Tamboril")
      expect(field("Provincia").value).toBe("Santiago")
      expect(field("Región").value).toBe("Región Norte o Cibao")
      expect(field("País").value).toBe("República Dominicana")
    })

    it("elegir una provincia llena Región y País, y deja Municipio vacío", async () => {
      renderPicker()
      const user = userEvent.setup()
      await ready()

      await user.click(field("Provincia"))
      await user.click(within(listFor("Provincia")).getByRole("option", { name: /Peravia/ }))

      expect(field("Provincia").value).toBe("Peravia")
      expect(field("Región").value).toBe("Región Sur")
      expect(field("País").value).toBe("República Dominicana")
      expect(field("Municipio").value).toBe("")
    })

    it("con provincia elegida, Municipio solo ofrece los suyos", async () => {
      renderPicker()
      const user = userEvent.setup()
      await ready()

      await user.click(field("Provincia"))
      await user.click(within(listFor("Provincia")).getByRole("option", { name: /Santiago/ }))
      await user.click(field("Municipio"))

      const list = listFor("Municipio")
      expect(within(list).getByRole("option", { name: /Tamboril/ })).toBeTruthy()
      expect(within(list).queryByRole("option", { name: /Baní/ })).toBeNull()
    })

    it("limpiar un campo limpia los de abajo pero conserva los de arriba", async () => {
      renderPicker()
      const user = userEvent.setup()
      await ready()

      await user.click(field("Municipio"))
      await user.type(field("Municipio"), "tamboril")
      await user.click(within(listFor("Municipio")).getByRole("option", { name: /Tamboril/ }))

      await user.click(screen.getByRole("button", { name: "Limpiar Provincia" }))

      expect(field("Provincia").value).toBe("")
      expect(field("Municipio").value).toBe("")
      expect(field("Región").value).toBe("Región Norte o Cibao")
      expect(field("País").value).toBe("República Dominicana")
    })
  })

  describe("agregar", () => {
    it("envía el nodo más específico elegido", async () => {
      const onAdd = renderPicker()
      const user = userEvent.setup()
      await ready()

      await user.click(field("Municipio"))
      await user.type(field("Municipio"), "tamboril")
      await user.click(within(listFor("Municipio")).getByRole("option", { name: /Tamboril/ }))
      await user.click(screen.getByRole("button", { name: /agregar/i }))

      expect(onAdd).toHaveBeenCalledWith(
        expect.objectContaining({ locality_id: 5, kind: "HECHO" })
      )
    })

    it("elegir solo el país es ámbito nacional", async () => {
      const onAdd = renderPicker()
      const user = userEvent.setup()
      await ready()

      await user.click(field("País"))
      await user.click(
        within(listFor("País")).getByRole("option", { name: /República Dominicana/ })
      )
      await user.click(screen.getByRole("button", { name: /agregar/i }))

      expect(onAdd).toHaveBeenCalledWith(expect.objectContaining({ locality_id: 1 }))
    })

    it("no permite agregar sin haber elegido nada", async () => {
      renderPicker()
      await ready()

      const button = screen.getByRole("button", { name: /agregar/i }) as HTMLButtonElement
      expect(button.disabled).toBe(true)
    })

    it("se puede elegir con el teclado", async () => {
      const onAdd = renderPicker()
      const user = userEvent.setup()
      await ready()

      await user.click(field("Municipio"))
      await user.type(field("Municipio"), "bani")
      await user.keyboard("{ArrowDown}{Enter}")
      await user.click(screen.getByRole("button", { name: /agregar/i }))

      expect(onAdd).toHaveBeenCalledWith(expect.objectContaining({ locality_id: 11 }))
    })
  })
})
