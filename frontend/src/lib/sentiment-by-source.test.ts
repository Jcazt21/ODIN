import { describe, expect, it } from "vitest"
import { groupArticlesBySource, groupSentimentBySource } from "@/lib/sentiment-by-source"
import type { CanonicalEntityArticleMention } from "@/lib/odin-api"

/** Desglose del sentimiento hacia una entidad, por medio (R3: qué trato le da
 *  cada periódico a cada actor). */

function mention(
  source: string,
  sentiment: string | null,
  mentions_count = 1,
  source_name?: string
): CanonicalEntityArticleMention {
  return {
    article_id: Math.random(),
    title: "t",
    url: "u",
    source,
    source_name: source_name ?? source,
    published_at: null,
    sentiment_toward: sentiment,
    sentiment_score: 1,
    mentions_count,
  } as unknown as CanonicalEntityArticleMention
}

describe("groupSentimentBySource", () => {
  it("separa un grupo por medio", () => {
    const rows = groupSentimentBySource([
      mention("listin_diario", "POS", 3, "Listín Diario"),
      mention("diario_libre", "NEG", 2, "Diario Libre"),
    ])

    expect(rows.map((r) => r.source)).toEqual(["listin_diario", "diario_libre"])
    expect(rows[0].sourceName).toBe("Listín Diario")
  })

  it("ordena por volumen de menciones, de mayor a menor", () => {
    const rows = groupSentimentBySource([
      mention("acento", "NEG", 5),
      mention("diario_libre", "POS", 28),
      mention("n_digital", "NEU", 2),
    ])

    expect(rows.map((r) => r.source)).toEqual(["diario_libre", "acento", "n_digital"])
  })

  it("usa la misma agregación que la barra global", () => {
    /* Que los porcentajes por medio y el total salgan de la misma función es
       lo que evita que no cuadren entre sí. */
    const rows = groupSentimentBySource([
      mention("hoy", "POS", 3),
      mention("hoy", "NEG", 1),
    ])

    expect(rows).toHaveLength(1)
    expect(Math.round(rows[0].aggregate.positivePct)).toBe(75)
    expect(Math.round(rows[0].aggregate.negativePct)).toBe(25)
  })

  it("marca como muestra baja al medio con pocas menciones", () => {
    const rows = groupSentimentBySource([
      mention("diario_libre", "POS", 28),
      mention("acento", "NEG", 1),
    ])

    expect(rows.find((r) => r.source === "diario_libre")!.aggregate.lowSample).toBe(false)
    expect(rows.find((r) => r.source === "acento")!.aggregate.lowSample).toBe(true)
  })

  it("descarta los medios sin ninguna mención con sentimiento", () => {
    const rows = groupSentimentBySource([
      mention("hoy", "POS", 2),
      mention("el_caribe", null, 4),
    ])

    expect(rows.map((r) => r.source)).toEqual(["hoy"])
  })

  it("sin nada utilizable devuelve una lista vacía", () => {
    expect(groupSentimentBySource([])).toEqual([])
    expect(groupSentimentBySource([mention("hoy", null)])).toEqual([])
  })
})

describe("groupArticlesBySource", () => {
  it("agrupa los artículos por medio", () => {
    const grupos = groupArticlesBySource([
      mention("listin_diario", "POS", 1, "Listín Diario"),
      mention("diario_libre", "NEG", 1, "Diario Libre"),
      mention("listin_diario", "NEU", 1, "Listín Diario"),
    ])

    expect(grupos).toHaveLength(2)
    expect(grupos.find((g) => g.source === "listin_diario")!.articles).toHaveLength(2)
  })

  it("ordena los grupos igual que el desglose: por volumen de menciones", () => {
    /* Que las dos secciones vayan en el mismo orden es lo que deja bajar del
       porcentaje de un medio directo a sus notas. */
    const articles = [
      mention("acento", "NEG", 5),
      mention("diario_libre", "POS", 28),
      mention("n_digital", "NEU", 2),
    ]

    expect(groupArticlesBySource(articles).map((g) => g.source)).toEqual(
      groupSentimentBySource(articles).map((r) => r.source)
    )
  })

  it("conserva el orden por fecha dentro de cada grupo", () => {
    const grupos = groupArticlesBySource([
      { ...mention("hoy", "POS", 1), title: "reciente" },
      { ...mention("hoy", "POS", 1), title: "vieja" },
    ])

    expect(grupos[0].articles.map((a) => a.title)).toEqual(["reciente", "vieja"])
  })

  it("mantiene el mismo orden aunque haya menciones sin sentimiento", () => {
    /* El desglose pesa solo las menciones CON sentimiento. Si acá se pesaran
       todas, un medio con mucho volumen sin analizar subiría en una lista y no
       en la otra, y las dos secciones dejarían de leerse en paralelo. */
    const articles = [
      mention("hoy", null, 50),        // mucho volumen, nada analizado
      mention("hoy", "POS", 2),
      mention("diario_libre", "POS", 10),
    ]

    expect(groupArticlesBySource(articles).map((g) => g.source)).toEqual(
      groupSentimentBySource(articles).map((r) => r.source)
    )
  })

  it("incluye medios sin sentimiento, que el desglose descarta", () => {
    /* La lista es "dónde se lo mencionó", no "cómo se lo trató". */
    const articles = [mention("hoy", "POS", 3), mention("el_caribe", null, 4)]

    expect(groupArticlesBySource(articles).map((g) => g.source)).toContain("el_caribe")
    expect(groupSentimentBySource(articles).map((r) => r.source)).not.toContain("el_caribe")
  })
})
