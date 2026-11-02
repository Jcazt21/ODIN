/// <reference types="node" />
import { readFileSync } from "node:fs"
import { join } from "node:path"

export const css = readFileSync(join(__dirname, "..", "index.css"), "utf8")

/** Cuerpo de un bloque `selector { ... }` de nivel superior. */
export function block(selector: string): string {
  const start = css.indexOf(`\n${selector} {`)
  if (start === -1) throw new Error(`sin bloque ${selector}`)
  return css.slice(start, css.indexOf("\n}", start))
}

export function token(body: string, name: string): string {
  const m = body.match(new RegExp(`${name}:\\s*([^;]+);`))
  if (!m) throw new Error(`${name} sin definir`)
  return m[1].trim()
}

export type Oklch = [number, number, number]

export function parseOklch(value: string): Oklch {
  const m = value.match(/^oklch\(\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*\)$/)
  if (!m) throw new Error(`se esperaba oklch(L C h) literal, no "${value}"`)
  return [Number(m[1]), Number(m[2]), Number(m[3])]
}

// Mismo cálculo que scratchpad/contrast.py: OKLCH -> sRGB lineal -> luminancia WCAG.
export function luminance([L, C, h]: Oklch): number {
  const a = C * Math.cos((h * Math.PI) / 180)
  const b = C * Math.sin((h * Math.PI) / 180)
  const l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
  const m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
  const s = (L - 0.0894841775 * a - 1.291485548 * b) ** 3
  const clamp = (x: number) => Math.min(1, Math.max(0, x))
  const r = clamp(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s)
  const g = clamp(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s)
  const bl = clamp(-0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s)
  return 0.2126 * r + 0.7152 * g + 0.0722 * bl
}

export function contrast(a: Oklch, b: Oklch): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}
