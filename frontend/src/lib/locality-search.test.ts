import { describe, expect, it } from "vitest"
import { filterLocalities, type LocalityEntry } from "@/lib/localities"

/** Búsqueda de localidades: coincide por INICIO DE PALABRA, no en cualquier
 *  posición.
 *
 *  Antes bastaba con que la letras aparecieran en algún lado, así que teclear
 *  "Al" en los municipios de Monte Cristi devolvía "Pepillo Salcedo" —coincide
 *  dentro de "sALcedo"— y la búsqueda parecía traer cosas al azar.
 */

function entry(name: string, aliases: string[] = []): LocalityEntry {
  const norm = (t: string) => t.normalize("NFD").replace(/\p{Mn}/gu, "").toLowerCase().trim()
  return {
    id: name.length,
    name,
    level: "MUNICIPIO",
    ancestors: [],
    breadcrumb: name,
    haystack: [name, ...aliases].map(norm),
  }
}

const MUNICIPIOS = [
  entry("Monte Cristi"),
  entry("Castañuelas"),
  entry("Guayubín"),
  entry("Las Matas de Santa Cruz"),
  entry("Pepillo Salcedo"),
  entry("Villa Vásquez"),
  entry("Villa Bisonó", ["Navarrete"]),
]

const names = (q: string) => filterLocalities(MUNICIPIOS, q).map((e) => e.name)

describe("filterLocalities", () => {
  it("no coincide en medio de una palabra", () => {
    expect(names("Al")).toEqual([])
  })

  it("coincide con el principio de una palabra interna", () => {
    expect(names("Sal")).toEqual(["Pepillo Salcedo"])
    expect(names("Mat")).toEqual(["Las Matas de Santa Cruz"])
  })

  it("coincide con el principio del nombre", () => {
    expect(names("Monte")).toEqual(["Monte Cristi"])
  })

  it("prioriza lo que empieza con lo tecleado", () => {
    /* "Villa" abre dos; ambos empiezan igual, así que se conserva el orden de
       entrada. Lo que importa es que un match de palabra interna nunca quede
       por encima de uno del principio. */
    expect(names("Villa")).toEqual(["Villa Vásquez", "Villa Bisonó"])
  })

  it("ignora acentos en las dos direcciones", () => {
    expect(names("guayubin")).toEqual(["Guayubín"])
    expect(names("Vásquez")).toEqual(["Villa Vásquez"])
  })

  it("encuentra por alias", () => {
    expect(names("navarrete")).toEqual(["Villa Bisonó"])
  })

  it("admite varias palabras", () => {
    expect(names("santa cruz")).toEqual(["Las Matas de Santa Cruz"])
  })

  it("sin texto devuelve todo", () => {
    expect(filterLocalities(MUNICIPIOS, "")).toHaveLength(MUNICIPIOS.length)
  })
})
