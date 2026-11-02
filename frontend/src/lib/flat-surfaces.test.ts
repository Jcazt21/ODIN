/// <reference types="node" />
import { describe, expect, it } from "vitest"
import { readFileSync } from "node:fs"
import { join } from "node:path"

const css = readFileSync(join(__dirname, "..", "index.css"), "utf8")

/** Cuerpo de un bloque `selector { ... }` de nivel superior. */
function block(selector: string): string {
  const start = css.indexOf(`\n${selector} {`)
  if (start === -1) throw new Error(`sin bloque ${selector}`)
  return css.slice(start, css.indexOf("\n}", start))
}

function hueOf(body: string): string {
  const m = body.match(/--primary:\s*oklch\(\s*[\d.]+\s+[\d.]+\s+([\d.]+)\s*\)/)
  if (!m) throw new Error("--primary debe estar en oklch")
  return m[1]
}

describe("superficies planas", () => {
  it("no usa backdrop-filter ni variables de vidrio", () => {
    expect(css).not.toContain("backdrop-filter")
    expect(css).not.toContain("--glass-")
  })

  it("las sombras no llevan brillo inset", () => {
    expect(css).not.toMatch(/--shadow(-sm)?:[^;]*inset 0 1px 0/)
  })

  it("--radius es ≥ 0.75rem (controles 12px, tarjetas 16px)", () => {
    const m = block(":root").match(/--radius:\s*([\d.]+)rem/)
    expect(m).not.toBeNull()
    expect(Number(m![1])).toBeGreaterThanOrEqual(0.75)
  })

  it("--shadow-sm tiene desfase vertical y desenfoque", () => {
    const m = block(":root").match(/--shadow-sm:\s*(-?[\d.]+)(?:px)?\s+(-?[\d.]+)px\s+(-?[\d.]+)px/)
    expect(m).not.toBeNull()
    expect(Number(m![2])).toBeGreaterThan(0)
    expect(Number(m![3])).toBeGreaterThan(Number(m![2]))
  })

  it("no deja keyframes huérfanos de odinShimmer", () => {
    if (!css.includes("@keyframes odinShimmer")) return
    expect(readFileSync(join(__dirname, "..", "components", "LoginScreen.tsx"), "utf8")).toContain("odinShimmer")
  })

})

describe("un solo acento", () => {
  it("claro y oscuro comparten el mismo hue", () => {
    expect(hueOf(block(":root"))).toBe(hueOf(block('[data-theme="dark"]')))
  })

  it("no define variantes data-accent", () => {
    expect(css).not.toContain("data-accent")
  })
})
