/// <reference types="node" />
import { describe, expect, it } from "vitest"
import { readFileSync, readdirSync, statSync } from "node:fs"
import { join } from "node:path"

/** Todo color de producción sale de un token: un valor literal no se adapta al
 *  tema dark. Excepciones legítimas: se listan acá con su motivo. */
const SRC = join(__dirname, "..")
const ALLOWED: string[] = [
  // Ilustración del interruptor (sol/luna/nubes): paleta fija, no semántica.
  "src/components/ui/sky-toggle.css",
]

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) return walk(path)
    return /\.(tsx?|css)$/.test(name) ? [path] : []
  })
}

const COLOR = /#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?)\(/g

describe("colores literales", () => {
  it("la producción usa solo tokens", () => {
    const offenders: string[] = []
    for (const file of walk(SRC)) {
      const rel = file.replace(SRC, "src")
      if (file.includes(".test.") || file.includes("/test/") || ALLOWED.includes(rel)) continue
      let text = readFileSync(file, "utf8")
      if (file.endsWith(".css")) {
        // Las definiciones de tokens viven en :root / [data-theme]; el resto no.
        text = text.replace(/(^|\n)(:root|\[data-theme="[a-z]+"\])[^{]*\{[\s\S]*?\n\}/g, "$1")
      }
      text = text.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "")
      for (const m of text.matchAll(COLOR)) offenders.push(`${rel}: ${m[0]}`)
    }
    expect(offenders).toEqual([])
  })
})
