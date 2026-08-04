import { Badge } from "@/components/ui/badge"
import { SENTIMENT_LABELS } from "@/lib/labels"

const TONE_VAR: Record<string, string> = {
  POS: "pos",
  NEG: "neg",
  NEU: "neu",
}

export function SentimentBadge({
  sentiment,
  score,
}: {
  sentiment: string | null
  score?: number | null
}) {
  const key = sentiment ?? "NEU"
  const tone = TONE_VAR[key] ?? "neu"
  return (
    <Badge
      variant="outline"
      className="font-medium"
      style={{
        background: `var(--${tone}-soft)`,
        color: `var(--${tone})`,
        borderColor: `var(--${tone})`,
      }}
    >
      {SENTIMENT_LABELS[key] ?? key}
      {typeof score === "number" && key !== "NEU" && (
        <span className="ml-1 opacity-70">· {Math.round(score * 100)}%</span>
      )}
    </Badge>
  )
}
