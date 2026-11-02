import { render } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { SourceLogo } from "@/components/SourceLogo"
import { sourceLogo } from "@/lib/source-logos"

const SLUGS = [
  "listin_diario", "diario_libre", "el_nacional", "hoy", "el_caribe",
  "al_momento", "el_dia", "n_digital", "acento",
]

describe("source logos", () => {
  it("cubre los nueve medios del rastreo", () => {
    for (const slug of SLUGS) expect(sourceLogo(slug), slug).toBeTruthy()
  })

  it("no inventa íconos para medios desconocidos", () => {
    expect(sourceLogo("medio_x")).toBeUndefined()
    expect(sourceLogo(null)).toBeUndefined()
  })

  it("renderiza decorativo, sin alt", () => {
    const { container } = render(<SourceLogo source="listin_diario" />)
    expect(container.querySelector("img")?.getAttribute("alt")).toBe("")
  })

  it("no renderiza nada sin ícono", () => {
    const { container } = render(<SourceLogo source="medio_x" />)
    expect(container.firstChild).toBeNull()
  })
})
