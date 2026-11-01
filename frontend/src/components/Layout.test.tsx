import { render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { describe, expect, it } from "vitest"
import { DialogProvider } from "@/lib/dialog"
import { Layout } from "./Layout"

function setup(path = "/analyze") {
  render(
    <DialogProvider>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route element={<Layout onLogout={() => {}} theme="light" onToggleTheme={() => {}} />}>
            <Route path="/analyze" element={<p>Pantalla analizar</p>} />
            <Route path="/reports" element={<p>Pantalla reportes</p>} />
            <Route path="/reports/new" element={<p>Pantalla nuevo</p>} />
            <Route path="/reports/:id" element={<p>Pantalla detalle</p>} />
            <Route path="/entities" element={<p>Pantalla entidades</p>} />
            <Route path="/aliases" element={<p>Pantalla siglas</p>} />
            <Route path="/documentalists" element={<p>Pantalla documentalistas</p>} />
            <Route path="/authors" element={<p>Pantalla autores</p>} />
            <Route path="/topics" element={<p>Pantalla temas</p>} />
            <Route path="/settings" element={<p>Pantalla ajustes</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </DialogProvider>
  )
}

describe("Layout — hoja de contenido", () => {
  it("el contenido de la ruta vive dentro de <main>", () => {
    setup()
    expect(screen.getByRole("main")).toContainElement(screen.getByText("Pantalla analizar"))
  })

  it("<main> es la región desplazable y se alcanza con teclado", () => {
    setup()
    const main = screen.getByRole("main")
    expect(main).toHaveAttribute("tabindex", "0")
    expect(main).toHaveAccessibleName("Contenido")
  })

  it("Reportes (tabla) se alinea a la izquierda y usa el ancho de la hoja; las páginas de lectura se centran", () => {
    setup("/reports")
    const wrapper = screen.getByText("Pantalla reportes").parentElement!.parentElement!
    expect(wrapper).not.toHaveClass("mx-auto")
    expect(wrapper.className).not.toMatch(/max-w-\[/)
  })

  it("el detalle de un reporte usa todo el ancho de la hoja, igual que la tabla", () => {
    setup("/reports/12")
    const wrapper = screen.getByText("Pantalla detalle").parentElement!.parentElement!
    expect(wrapper).not.toHaveClass("mx-auto")
    expect(wrapper.className).not.toMatch(/max-w-\[/)
  })

  it.each([
    ["/analyze", "Pantalla analizar"],
    ["/entities", "Pantalla entidades"],
    ["/aliases", "Pantalla siglas"],
    ["/documentalists", "Pantalla documentalistas"],
    ["/authors", "Pantalla autores"],
    ["/topics", "Pantalla temas"],
  ])("ninguna ruta se centra: %s", (path, text) => {
    setup(path)
    const wrapper = screen.getByText(text).parentElement!.parentElement!
    expect(wrapper).not.toHaveClass("mx-auto")
    expect(wrapper.className).not.toMatch(/max-w-\[/)
  })

  it.each([
    ["/reports/new", "Pantalla nuevo"],
    ["/settings", "Pantalla ajustes"],
  ])("formularios largos: max-w sin centrar: %s", (path, text) => {
    setup(path)
    const wrapper = screen.getByText(text).parentElement!.parentElement!
    expect(wrapper).not.toHaveClass("mx-auto")
    expect(wrapper.className).toMatch(/max-w-\[/)
  })

  it("cada ruta remonta el contenedor con la animación de entrada", () => {
    setup("/reports")
    expect(screen.getByText("Pantalla reportes").parentElement).toHaveClass("odin-enter")
  })
})
