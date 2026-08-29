import { computeSentimentAggregate, type SentimentAggregate } from "@/lib/sentiment-aggregate"
import type { CanonicalEntityArticleMention } from "@/lib/odin-api"

export interface SourceSentiment {
  source: string
  sourceName: string
  aggregate: SentimentAggregate
}

/** Sentimiento hacia una entidad, desglosado por medio (R3: qué trato le da
 *  cada periódico a cada actor).
 *
 *  Reusa `computeSentimentAggregate`, la misma función que alimenta la barra
 *  global, y no una cuenta propia: si cada una ponderara distinto, los
 *  porcentajes por medio no cuadrarían con el total y no habría forma de saber
 *  cuál de los dos mirar.
 *
 *  Se ordena por volumen de menciones porque lo mejor respaldado es lo que hay
 *  que leer primero; los medios de una sola nota quedan abajo y además llegan
 *  con `lowSample` encendido para que la interfaz los marque.
 *
 *  Un medio sin ninguna mención con sentimiento se descarta: una fila vacía no
 *  dice nada sobre su trato hacia la entidad.
 */
export interface SourceArticles {
  source: string
  sourceName: string
  articles: CanonicalEntityArticleMention[]
}

/** Los artículos de una entidad, agrupados por medio.
 *
 *  Mismo orden que `groupSentimentBySource` —por volumen de menciones— para
 *  que las dos secciones de la ficha se lean en paralelo: del porcentaje de un
 *  medio se baja directo a sus notas.
 *
 *  A diferencia del desglose, acá SÍ entran los medios sin ninguna mención con
 *  sentimiento: esta lista responde "dónde se lo mencionó", no "cómo se lo
 *  trató". Dentro de cada grupo se conserva el orden que trae el backend, que
 *  es por fecha descendente.
 */
export function groupArticlesBySource(
  articles: CanonicalEntityArticleMention[]
): SourceArticles[] {
  return [...bySource(articles)]
    .map(([source, group]) => ({
      source,
      sourceName: group[0].source_name || source,
      articles: group,
    }))
    .sort((a, b) => ratedMentionVolume(b.articles) - ratedMentionVolume(a.articles))
}

/** Menciones CON sentimiento de un grupo.
 *
 *  Se ignoran las no analizadas a propósito: es la misma medida con la que
 *  `computeSentimentAggregate` llena `sampleSize`, y usar otra haría que un
 *  medio con mucho volumen sin analizar subiera en una lista y no en la otra.
 *  Un medio sin nada analizado da 0 y queda al final, que es donde va.
 */
function ratedMentionVolume(articles: CanonicalEntityArticleMention[]): number {
  return articles.reduce(
    (sum, a) => (a.sentiment_toward ? sum + Math.max(1, a.mentions_count) : sum),
    0
  )
}

function bySource(
  articles: CanonicalEntityArticleMention[]
): Map<string, CanonicalEntityArticleMention[]> {
  const out = new Map<string, CanonicalEntityArticleMention[]>()
  for (const article of articles) {
    const list = out.get(article.source)
    if (list) list.push(article)
    else out.set(article.source, [article])
  }
  return out
}

export function groupSentimentBySource(
  articles: CanonicalEntityArticleMention[]
): SourceSentiment[] {
  const rows: SourceSentiment[] = []
  for (const [source, group] of bySource(articles)) {
    const aggregate = computeSentimentAggregate(group)
    if (!aggregate) continue
    rows.push({
      source,
      sourceName: group[0].source_name || source,
      aggregate,
    })
  }

  return rows.sort((a, b) => b.aggregate.sampleSize - a.aggregate.sampleSize)
}
