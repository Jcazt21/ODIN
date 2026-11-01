import { describe, expect, it } from "vitest"
import { block, contrast, parseOklch, token } from "./oklch-test-utils"

const dark = block('[data-theme="dark"]')
const light = block(":root")
const L = (name: string, body = dark) => parseOklch(token(body, name))[0]

describe("paleta dark", () => {
  it("fondo dark profundo y no negro", () => {
    const [l, c] = parseOklch(token(dark, "--bg"))
    expect(l).toBeGreaterThanOrEqual(0.12)
    expect(l).toBeLessThanOrEqual(0.16)
    expect(c).toBeLessThanOrEqual(0.02)
  })

  it("superficies escalonadas", () => {
    const names = ["--bg", "--surface", "--surface-2", "--surface-3", "--border"]
    for (let i = 1; i < names.length; i++) {
      expect(L(names[i]) - L(names[i - 1]), names[i]).toBeGreaterThanOrEqual(0.025)
    }
  })

  it("texto no blanco puro", () => {
    const text = parseOklch(token(dark, "--text"))
    expect(text[0]).toBeLessThanOrEqual(0.96)
    const ratio = contrast(text, parseOklch(token(dark, "--bg")))
    expect(ratio).toBeGreaterThanOrEqual(7)
    expect(ratio).toBeLessThanOrEqual(18)
  })

  it("semánticos: rangos y contraste ≥ 4.5", () => {
    const surface = parseOklch(token(dark, "--surface"))
    for (const name of ["pos", "neg", "warn", "neu"]) {
      const fg = parseOklch(token(dark, `--${name}`))
      expect(contrast(fg, surface), `${name}/surface`).toBeGreaterThanOrEqual(4.5)
      const soft = parseOklch(token(dark, `--${name}-soft`))
      expect(contrast(fg, soft), `${name}/soft`).toBeGreaterThanOrEqual(4.5)
      expect(soft[0], `${name}-soft L`).toBeLessThanOrEqual(0.3)
    }
    const [pl, pc, ph] = parseOklch(token(dark, "--pos"))
    expect(ph).toBeGreaterThanOrEqual(145); expect(ph).toBeLessThanOrEqual(160)
    expect(pc).toBeGreaterThanOrEqual(0.17); expect(pc).toBeLessThanOrEqual(0.2)
    expect(pl).toBeLessThanOrEqual(0.82)
    const [nl, nc, nh] = parseOklch(token(dark, "--neg"))
    expect(nh).toBeGreaterThanOrEqual(18); expect(nh).toBeLessThanOrEqual(26)
    expect(nc).toBeGreaterThanOrEqual(0.17); expect(nc).toBeLessThanOrEqual(0.2)
    expect(nl).toBeGreaterThanOrEqual(0.7); expect(nl).toBeLessThanOrEqual(0.76)
    expect(L("--warn")).toBeLessThanOrEqual(0.86)
  })

  it("shell más oscuro", () => {
    expect(Math.abs(L("--shell-from") - 0.15)).toBeLessThanOrEqual(0.02)
    expect(Math.abs(L("--shell-to") - 0.22)).toBeLessThanOrEqual(0.02)
  })

  it("light mode sin cambios", () => {
    const expected: Record<string, string> = {
      "--bg": "oklch(0.963 0.004 195)",
      "--surface": "oklch(0.988 0.003 195)",
      "--pos": "oklch(0.47 0.12 135)",
      "--neg": "oklch(0.5 0.16 25)",
      "--warn": "oklch(0.52 0.12 75)",
      "--neu": "oklch(0.5 0.012 195)",
    }
    for (const [k, v] of Object.entries(expected)) expect(token(light, k), k).toBe(v)
  })
})
