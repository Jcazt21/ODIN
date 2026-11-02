/// <reference types="node" />
import { describe, expect, it } from "vitest"
import { readFileSync, readdirSync, statSync } from "node:fs"
import { join } from "node:path"

const SRC = join(__dirname, "..")

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) return walk(path)
    return /\.(tsx?|css)$/.test(name) ? [path] : []
  })
}

describe("superficies heredadas", () => {
  it("no queda odin-glass", () => {
    const offenders = walk(SRC)
      .filter((f) => !f.includes(".test."))
      .filter((f) => readFileSync(f, "utf8").includes("odin-glass"))
    expect(offenders).toEqual([])
  })
})
