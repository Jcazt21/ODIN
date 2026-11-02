import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { ExpandableRow } from "./ExpandableRow"

function Child({ onMount }: { onMount: () => void }) {
  onMount()
  return <p>Detalle de la fila</p>
}

function setup(onMount = vi.fn()) {
  render(
    <table>
      <tbody>
        <ExpandableRow label="Ana Pérez" colSpan={3} cells={<td>celda</td>}>
          <Child onMount={onMount} />
        </ExpandableRow>
      </tbody>
    </table>
  )
  return onMount
}

describe("ExpandableRow", () => {
  it("el chevron es un botón con aria-expanded y el contenido no existe colapsado", () => {
    const onMount = setup()
    const button = screen.getByRole("button", { name: /Ana Pérez/ })
    expect(button).toHaveAttribute("aria-expanded", "false")
    expect(screen.queryByText("Detalle de la fila")).not.toBeInTheDocument()
    expect(onMount).not.toHaveBeenCalled()
  })

  it("clic, Enter y Espacio expanden y colapsan", async () => {
    const user = userEvent.setup()
    setup()
    const button = screen.getByRole("button", { name: /Ana Pérez/ })
    await user.click(button)
    expect(button).toHaveAttribute("aria-expanded", "true")
    expect(screen.getByText("Detalle de la fila")).toBeInTheDocument()
    button.focus()
    await user.keyboard("{Enter}")
    expect(screen.queryByText("Detalle de la fila")).not.toBeInTheDocument()
    await user.keyboard(" ")
    expect(screen.getByText("Detalle de la fila")).toBeInTheDocument()
  })
})
