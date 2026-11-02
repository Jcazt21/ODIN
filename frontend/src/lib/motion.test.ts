/// <reference types="node" />
import { describe, expect, it } from "vitest"
import { readFileSync, readdirSync, statSync } from "node:fs"
import { join } from "node:path"

/** Contratos de movimiento: solo propiedades de compositor, easing de salida,
 *  y reduced-motion que conserva el fundido. El resto (que se sienta bien) se
 *  mira en el navegador. */

const SRC = join(__dirname, "..")
const css = readFileSync(join(SRC, "index.css"), "utf8")
const read = (rel: string) => readFileSync(join(SRC, rel), "utf8")

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) return walk(path)
    return /\.(tsx?|css)$/.test(name) && !name.includes(".test.") ? [path] : []
  })
}

function keyframes(): Record<string, string> {
  const out: Record<string, string> = {}
  for (const m of css.matchAll(/@keyframes\s+(\w+)\s*\{((?:[^{}]|\{[^}]*\})*)\}/g)) out[m[1]] = m[2]
  return out
}

describe("movimiento", () => {
  it("ningún componente anima todas las propiedades ni usa ease-in", () => {
    const offenders = walk(SRC).filter((f) => /transition-all|\bease-in\b(?!-)/.test(readFileSync(f, "utf8")))
    expect(offenders.map((f) => f.replace(SRC, "src"))).toEqual([])
  })

  it("los keyframes de entrada solo tocan opacity y transform", () => {
    const entering = ["odinIn", "odinPop", "odinFade"]
    const all = keyframes()
    for (const name of entering) {
      expect(all[name], `falta @keyframes ${name}`).toBeDefined()
      const props = [...all[name].matchAll(/([a-z-]+)\s*:/g)].map((m) => m[1])
      expect(props.filter((p) => p !== "opacity" && p !== "transform")).toEqual([])
    }
  })

  it("define la curva ease-out fuerte y las clases de entrada", () => {
    expect(css).toMatch(/--ease-out:\s*cubic-bezier\(0\.23,\s*1,\s*0\.32,\s*1\)/)
    expect(css).toMatch(/\.odin-enter\s*\{/)
    expect(css).toMatch(/\.odin-pop\s*\{/)
  })

  it("reduced-motion conserva el fundido y quita el desplazamiento", () => {
    const block = css.slice(css.indexOf("@media (prefers-reduced-motion"))
    expect(block).toMatch(/\.odin-enter[^{]*\{[^}]*animation-name:\s*odinFade/)
  })

  it("las entradas duran menos de 300ms", () => {
    for (const m of css.matchAll(/\.odin-(?:enter|pop)\s*\{[^}]*animation:[^;]*?(\d+)ms/g)) {
      expect(Number(m[1])).toBeLessThan(300)
    }
  })

  it("el diálogo usa la animación de entrada tipada, no un ease genérico", () => {
    expect(read("lib/dialog.tsx")).not.toMatch(/odinIn 0\.16s ease"/)
    expect(read("lib/dialog.tsx")).toContain("odin-pop")
  })

  it("las superficies que aparecen al vuelo llevan clase de entrada", () => {
    expect(read("components/Layout.tsx")).toContain("odin-enter")
    expect(read("components/ActionButtons.tsx")).toContain("odin-enter")
    expect(read("pages/ReportsPage.tsx")).toContain("odin-enter")
    expect(read("components/reports/FilterBar.tsx")).toContain("odin-pop")
  })

  it("la expansión de filas dura ≤ 200ms, solo opacity/grid-template-rows, y respeta reduced-motion", () => {
    const frames = keyframes().odinExpand
    expect(frames, "falta @keyframes odinExpand").toBeDefined()
    const props = [...frames.matchAll(/([a-z-]+)\s*:/g)].map((m) => m[1])
    expect(props.filter((p) => p !== "opacity" && p !== "grid-template-rows")).toEqual([])
    const m = css.match(/\.odin-expand\s*\{[^}]*animation:[^;]*?(\d+)ms/)
    expect(m, "falta .odin-expand").not.toBeNull()
    expect(Number(m![1])).toBeLessThanOrEqual(200)
    const reduced = css.slice(css.indexOf("@media (prefers-reduced-motion"))
    expect(reduced).toMatch(/\.odin-expand[^{]*\{[^}]*animation-name:\s*odinFade/)
  })
})
