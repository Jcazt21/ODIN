import { SENTIMENT_LABELS } from "@/lib/labels"

export const SENTIMENT_TONE: Record<string, "pos" | "neg" | "neu"> = { POS: "pos", NEG: "neg", NEU: "neu" }

/** Punto de color + texto, sin caja: se repite en cada fila y la píldora pesaba. */
export function SentimentDot({ sentiment, score }: { sentiment: string | null; score?: number | null }) {
  const key = sentiment ?? "NEU"
  const tone = SENTIMENT_TONE[key] ?? "neu"
  return (
    <span className="inline-flex items-center gap-1.5 font-medium" style={{ color: `var(--${tone})` }}>
      <span aria-hidden className="size-2 rounded-full" style={{ background: `var(--${tone})` }} />
      <span>{SENTIMENT_LABELS[key] ?? key}</span>
      {typeof score === "number" && key !== "NEU" && (
        <span className="opacity-70">· {Math.round(score * 100)}%</span>
      )}
    </span>
  )
}
