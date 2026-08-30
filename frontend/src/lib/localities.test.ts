import { describe, expect, it } from "vitest"
import { suggestedToPicked } from "@/lib/localities"

const sugerencia = {
  locality_id: 42,
  name: "Bajos de Haina",
  level: "MUNICIPIO",
  breadcrumb: [
    { id: 1, name: "República Dominicana", level: "PAIS" },
    { id: 9, name: "San Cristóbal", level: "PROVINCIA" },
    { id: 42, name: "Bajos de Haina", level: "MUNICIPIO" },
  ],
  kind: "HECHO",
  origin: "AUTO",
  confidence: 0.9,
  matched_text: "Haina",
}

describe("suggestedToPicked", () => {
  it("arma el mismo shape que consume el selector", () => {
    const [picked] = suggestedToPicked([sugerencia])
    expect(picked.locality_id).toBe(42)
    expect(picked.kind).toBe("HECHO")
    expect(picked.label).toBe("República Dominicana › San Cristóbal › Bajos de Haina")
  })

  it("conserva el origen AUTO y la confianza para que viajen al guardar", () => {
    const [picked] = suggestedToPicked([sugerencia])
    expect(picked.origin).toBe("AUTO")
    expect(picked.confidence).toBe(0.9)
  })

  it("cae al nombre suelto cuando no vino el camino", () => {
    const [picked] = suggestedToPicked([{ ...sugerencia, breadcrumb: [] }])
    expect(picked.label).toBe("Bajos de Haina")
  })
})
