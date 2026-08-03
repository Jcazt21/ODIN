import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

const LABELS: Record<string, string> = {
  POS: "Positivo",
  NEG: "Negativo",
  NEU: "Neutro",
}

const STYLES: Record<string, string> = {
  POS: "bg-success/15 text-success border-success/30",
  NEG: "bg-destructive/15 text-destructive border-destructive/30",
  NEU: "bg-muted text-muted-foreground border-border",
}

export function SentimentBadge({
  sentiment,
  score,
}: {
  sentiment: string | null
  score?: number | null
}) {
  const key = sentiment ?? "NEU"
  return (
    <Badge variant="outline" className={cn("font-medium", STYLES[key] ?? STYLES.NEU)}>
      {LABELS[key] ?? key}
      {typeof score === "number" && (
        <span className="ml-1 opacity-70">{Math.round(score * 100)}%</span>
      )}
    </Badge>
  )
}
