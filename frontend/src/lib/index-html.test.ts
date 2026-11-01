/// <reference types="node" />
import { expect, it } from "vitest"
import { readFileSync } from "node:fs"
import { join } from "node:path"

const html = readFileSync(join(__dirname, "..", "..", "index.html"), "utf8")

it("declara el idioma español", () => {
  expect(html).toMatch(/<html[^>]*lang="es"/)
})

it("no fija el tema oscuro con una clase", () => {
  expect(html).not.toMatch(/<html[^>]*class="dark"/)
})
