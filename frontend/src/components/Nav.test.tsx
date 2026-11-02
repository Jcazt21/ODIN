import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { describe, expect, it, vi } from "vitest"
import { DialogProvider } from "@/lib/dialog"
import { Nav } from "./Nav"

function setup(path = "/analyze", role?: string) {
  const onLogout = vi.fn()
  const onToggleTheme = vi.fn()
  render(
    <DialogProvider>
      <MemoryRouter initialEntries={[path]}>
        <Nav username="ana" role={role} theme="light" onToggleTheme={onToggleTheme} onLogout={onLogout} />
      </MemoryRouter>
    </DialogProvider>
  )
  return { onLogout, onToggleTheme, user: userEvent.setup() }
}

const userButton = () => screen.getByRole("button", { name: /ana/i })

describe("Nav — sidebar", () => {
  it("agrupa los enlaces en Principal, Administración y Cuenta", () => {
    setup()
    const groups: Record<string, string[]> = {
      Principal: ["Analizar", "Reportes"],
      Administración: ["Entidades", "Siglas", "Autores", "Temas", "Documentalistas"],
      Cuenta: ["Ajustes"],
    }
    for (const [group, links] of Object.entries(groups)) {
      const section = screen.getByRole("group", { name: group })
      expect(within(section).getAllByRole("link").map((l) => l.textContent)).toEqual(links)
    }
    expect(screen.queryByText("v2.2.2")).not.toBeInTheDocument()
  })

  it("incluye Autores y Temas con su ruta", () => {
    setup()
    expect(screen.getByRole("link", { name: "Autores" })).toHaveAttribute("href", "/authors")
    expect(screen.getByRole("link", { name: "Temas" })).toHaveAttribute("href", "/topics")
  })

  it("marca solo el enlace de la ruta actual", () => {
    setup("/reports/12")
    expect(screen.getByRole("link", { name: "Reportes" })).toHaveAttribute("aria-current", "page")
    expect(screen.getByRole("link", { name: "Analizar" })).not.toHaveAttribute("aria-current")
    expect(screen.getByRole("link", { name: "Entidades" })).not.toHaveAttribute("aria-current")
  })

  it("en una página de administración queda activa esa y no las principales", () => {
    setup("/entities")
    expect(screen.getByRole("link", { name: "Entidades" })).toHaveAttribute("aria-current", "page")
    expect(screen.getByRole("link", { name: "Reportes" })).not.toHaveAttribute("aria-current")
  })
})

describe("Nav — menú de usuario", () => {
  it("el bloque de cuenta queda al pie, después de la navegación, y muestra el rol", () => {
    setup()
    const nav = screen.getByRole("navigation", { name: "Navegación principal", hidden: true })
    expect(nav.compareDocumentPosition(userButton()) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(within(userButton()).getByText("Documentalista")).toBeInTheDocument()
  })

  it("muestra Administrador cuando el rol es admin", () => {
    setup("/analyze", "admin")
    expect(within(userButton()).getByText("Administrador")).toBeInTheDocument()
  })

  it("la tarjeta de usuario abre el menú con tema y cerrar sesión", async () => {
    const { user } = setup()
    await user.click(userButton())
    expect(await screen.findByRole("menu")).toBeInTheDocument()
    expect(await screen.findByRole("menuitem", { name: /tema/i })).toBeInTheDocument()
    expect(await screen.findByRole("menuitem", { name: "Cerrar sesión" })).toBeInTheDocument()
    expect(screen.queryByRole("menuitem", { name: "Entidades" })).not.toBeInTheDocument()
  })

  it("Escape cierra el menú, el foco va al primer ítem al abrir y vuelve al botón", async () => {
    const { user } = setup()
    await user.click(userButton())
    const first = await screen.findByRole("menuitem", { name: /tema/i })
    await waitFor(() => expect(first).toHaveFocus())
    await user.keyboard("{Escape}")
    await waitFor(() => expect(screen.queryByRole("menu")).not.toBeInTheDocument())
    await waitFor(() => expect(userButton()).toHaveFocus())
  })

  it("cambiar tema llama onToggleTheme", async () => {
    const { user, onToggleTheme } = setup()
    await user.click(userButton())
    await user.click(await screen.findByRole("menuitem", { name: /tema/i }))
    expect(onToggleTheme).toHaveBeenCalledTimes(1)
  })

  it("cerrar sesión pide confirmación y solo sale si se acepta", async () => {
    const { user, onLogout } = setup()
    await user.click(userButton())
    await user.click(await screen.findByRole("menuitem", { name: "Cerrar sesión" }))
    await user.click(await screen.findByRole("button", { name: "Cancelar" }))
    expect(onLogout).not.toHaveBeenCalled()

    await user.click(userButton())
    await user.click(await screen.findByRole("menuitem", { name: "Cerrar sesión" }))
    const dialog = await screen.findByRole("dialog")
    await user.click(within(dialog).getByRole("button", { name: "Cerrar sesión" }))
    expect(onLogout).toHaveBeenCalledTimes(1)
  })
})

describe("Nav — cajón en móvil", () => {
  const toggle = () => screen.getByRole("button", { name: /abrir menú|cerrar menú/i })

  it("el botón abre y cierra el cajón", async () => {
    const { user } = setup()
    expect(toggle()).toHaveAttribute("aria-expanded", "false")
    await user.click(toggle())
    expect(toggle()).toHaveAttribute("aria-expanded", "true")
    await user.click(toggle())
    expect(toggle()).toHaveAttribute("aria-expanded", "false")
  })

  it("Escape lo cierra y devuelve el foco al botón", async () => {
    const { user } = setup()
    await user.click(toggle())
    await user.keyboard("{Escape}")
    expect(toggle()).toHaveAttribute("aria-expanded", "false")
    expect(toggle()).toHaveFocus()
  })

  it("elegir un enlace cierra el cajón", async () => {
    const { user } = setup()
    await user.click(toggle())
    await user.click(screen.getByRole("link", { name: "Reportes" }))
    expect(toggle()).toHaveAttribute("aria-expanded", "false")
  })

  it("tocar el fondo lo cierra", async () => {
    const { user } = setup()
    await user.click(toggle())
    await user.click(screen.getByTestId("nav-backdrop"))
    expect(toggle()).toHaveAttribute("aria-expanded", "false")
  })
})
