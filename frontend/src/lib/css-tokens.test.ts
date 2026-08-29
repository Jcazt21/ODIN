/// <reference types="node" />
import { describe, expect, it } from "vitest"
import { readFileSync, readdirSync, statSync } from "node:fs"
import { join } from "node:path"

/** Cada `var(--token)` usado en el proyecto tiene que estar definido en algún
 *  `.css`.
 *
 *  Un token inexistente no falla ni avisa: `var()` sin definir invalida la
 *  declaración y el navegador la descarta en silencio. Con `background` el
 *  elemento queda TRANSPARENTE — le pasó al desplegable de lugares, que dejaba
 *  ver el contenido de atrás por decir `--surface-1`, que no existe — y con
 *  `color` el texto hereda el color de alrededor, que fue por qué los mensajes
 *  de error de tres formularios no se veían rojos (`--danger`, tampoco existe).
 *
 *  La directiva `/// <reference types="node" />` habilita `fs` solo acá: el
 *  tsconfig de la aplicación no incluye los tipos de Node a propósito, para que
 *  el código de producción no pueda usarlos por accidente.
 */

const SRC = join(__dirname, "..")

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) return walk(path)
    return /\.(tsx?|css)$/.test(name) ? [path] : []
  })
}

/** Definiciones de TODOS los .css, no solo index.css: hay componentes que
 *  declaran tokens propios en su hoja (sky-toggle.css). */
function definedTokens(files: string[]): Set<string> {
  const out = new Set<string>()
  for (const file of files.filter((f) => f.endsWith(".css"))) {
    for (const m of readFileSync(file, "utf8").matchAll(/(--[a-z0-9-]+)\s*:/gi)) {
      out.add(m[1])
    }
  }
  return out
}

describe("tokens CSS", () => {
  it("no se usa ningún token que no esté definido", () => {
    const files = walk(SRC)
    const defined = definedTokens(files)
    const offenders: string[] = []

    for (const file of files) {
      if (file.includes(".test.")) continue
      for (const m of readFileSync(file, "utf8").matchAll(/var\((--[a-z0-9-]+)/gi)) {
        // Los internos de Tailwind se declaran en su runtime, no en el proyecto.
        if (m[1].startsWith("--tw-")) continue
        offenders.push(defined.has(m[1]) ? "" : `${file.replace(SRC, "src")}: ${m[1]}`)
      }
    }

    expect(offenders.filter(Boolean)).toEqual([])
  })
})
