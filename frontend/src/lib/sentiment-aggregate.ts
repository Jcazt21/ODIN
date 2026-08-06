import type { CanonicalEntityArticleMention } from "@/lib/odin-api"

// Umbral bajo el cual el promedio se marca como "muestra baja": con pocas
// menciones, un par de artículos ruidosos puede mover el promedio entero.
const LOW_SAMPLE_THRESHOLD = 5

export interface SentimentAggregate {
  /** % de menciones (ponderadas por mentions_count) en cada categoría, suman ~100 */
  positivePct: number
  neutralPct: number
  negativePct: number
  /** Promedio ponderado en escala -1..+1 (POS=+1, NEU=0, NEG=-1, peso = mentions_count * confianza) */
  weightedScore: number
  dominant: "POS" | "NEU" | "NEG"
  sampleSize: number
  lowSample: boolean
}

export function computeSentimentAggregate(
  articles: CanonicalEntityArticleMention[]
): SentimentAggregate | null {
  const usable = articles.filter((a) => a.sentiment_toward)
  if (usable.length === 0) return null

  let posWeight = 0
  let neuWeight = 0
  let negWeight = 0
  let scoreSum = 0
  let weightSum = 0
  let sampleSize = 0

  for (const a of usable) {
    const count = Math.max(1, a.mentions_count)
    const confidence = typeof a.sentiment_score === "number" ? a.sentiment_score : 0.5
    const weight = count * confidence
    sampleSize += count

    if (a.sentiment_toward === "POS") {
      posWeight += weight
      scoreSum += weight * 1
    } else if (a.sentiment_toward === "NEG") {
      negWeight += weight
      scoreSum += weight * -1
    } else {
      neuWeight += weight
    }
    weightSum += weight
  }

  if (weightSum === 0) return null

  const positivePct = (posWeight / weightSum) * 100
  const neutralPct = (neuWeight / weightSum) * 100
  const negativePct = (negWeight / weightSum) * 100
  const weightedScore = scoreSum / weightSum

  const dominant: SentimentAggregate["dominant"] =
    posWeight >= neuWeight && posWeight >= negWeight
      ? "POS"
      : negWeight >= neuWeight
        ? "NEG"
        : "NEU"

  return {
    positivePct,
    neutralPct,
    negativePct,
    weightedScore,
    dominant,
    sampleSize,
    lowSample: sampleSize < LOW_SAMPLE_THRESHOLD,
  }
}
