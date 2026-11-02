/// <reference types="node" />
import { describe, expect, it } from "vitest"
import { block, contrast, parseOklch, token } from "./oklch-test-utils"

const themes: Record<string, string> = {
  claro: block(":root"),
  oscuro: block('[data-theme="dark"]'),
}

describe.each(Object.entries(themes))("tokens del shell — tema %s", (_name, body) => {
  it("define marco, hoja y colores del sidebar", () => {
    for (const name of ["--shell-from", "--shell-to", "--sidebar-foreground", "--sidebar-accent", "--sheet"]) {
      expect(body, name).toContain(`${name}:`)
    }
  })

  it("el texto del sidebar tiene contraste ≥ 4.5 contra ambos extremos del degradado", () => {
    const fg = parseOklch(token(body, "--sidebar-foreground"))
    expect(contrast(fg, parseOklch(token(body, "--shell-from")))).toBeGreaterThanOrEqual(4.5)
    expect(contrast(fg, parseOklch(token(body, "--shell-to")))).toBeGreaterThanOrEqual(4.5)
  })

  it("el ítem activo del sidebar tiene contraste ≥ 4.5", () => {
    const fg = parseOklch(token(body, "--sidebar-accent-foreground"))
    expect(contrast(fg, parseOklch(token(body, "--sidebar-accent")))).toBeGreaterThanOrEqual(4.5)
  })
})

describe("gradiente del shell", () => {
  it("--shell-gradient une los dos extremos", () => {
    expect(block(":root")).toMatch(/--shell-gradient:\s*linear-gradient\([^;]*--shell-from[^;]*--shell-to/)
  })
})
