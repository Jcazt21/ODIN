import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { LocalityCombobox } from "@/components/LocalityCombobox"
import type { LocalityEntry } from "@/lib/localities"

const ENTRIES: LocalityEntry[] = [
  {
    id: 10,
    name: "Azua",
    level: "PROVINCIA",
    ancestors: [{ id: 1, name: "República Dominicana", level: "PAIS" }] as LocalityEntry["ancestors"],
    breadcrumb: "República Dominicana › Azua",
    haystack: ["azua"],
  },
  {
    id: 11,
    name: "Bahoruco",
    level: "PROVINCIA",
    ancestors: [{ id: 1, name: "República Dominicana", level: "PAIS" }] as LocalityEntry["ancestors"],
    breadcrumb: "República Dominicana › Bahoruco",
    haystack: ["bahoruco"],
  },
]

/** Reproduce el anidado real: una tarjeta con `backdrop-filter`, que CREA un
 *  contexto de apilamiento, seguida de otra tarjeta hermana. */
function renderInsideCard() {
  render(
    <div>
      <div data-testid="tarjeta" className="odin-glass" style={{ backdropFilter: "blur(8px)" }}>
        <LocalityCombobox
          label="Provincia"
          entries={ENTRIES}
          selected={undefined}
          onSelect={vi.fn()}
        />
      </div>
      <div data-testid="tarjeta-siguiente">Figuras y empresas mencionadas</div>
    </div>
  )
}

describe("LocalityCombobox — capa del desplegable", () => {
  it("la lista no vive dentro de la tarjeta que la contiene", async () => {
    /* Una tarjeta con backdrop-filter crea un contexto de apilamiento propio:
       el z-index de la lista solo compite DENTRO de esa tarjeta, así que la
       tarjeta hermana siguiente la tapaba sin importar cuánto se subiera.
       Sacarla del árbol con un portal es lo único que la libera. */
    const user = userEvent.setup()
    renderInsideCard()

    await user.click(screen.getByLabelText("Provincia"))

    const lista = screen.getByRole("listbox", { name: "Opciones de Provincia" })
    expect(screen.getByTestId("tarjeta").contains(lista)).toBe(false)
  })

  it("sigue siendo alcanzable y usable", async () => {
    const onSelect = vi.fn()
    const user = userEvent.setup()
    render(
      <LocalityCombobox label="Provincia" entries={ENTRIES} selected={undefined} onSelect={onSelect} />
    )

    await user.click(screen.getByLabelText("Provincia"))
    await user.click(screen.getByRole("option", { name: /Azua/ }))

    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ id: 10 }))
  })
})
