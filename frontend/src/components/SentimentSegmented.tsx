import { cn } from "@/lib/utils"

const SENTIMENTS = ["NEG", "NEU", "POS"] as const
type Sentiment = (typeof SENTIMENTS)[number]

const ACTIVE_STYLES: Record<Sentiment, string> = {
  NEG: "bg-destructive/15 text-destructive border-destructive/40",
  NEU: "bg-muted-foreground/15 text-foreground border-muted-foreground/30",
  POS: "bg-success/15 text-success border-success/40",
}

export function SentimentSegmented({
  value,
  onChange,
  size = "default",
}: {
  value: Sentiment
  onChange: (value: Sentiment) => void
  size?: "default" | "sm"
}) {
  return (
    <div
      className={cn(
        "inline-flex gap-0.5 rounded-lg border border-border bg-muted/40 p-0.5",
        size === "sm" && "gap-px p-px"
      )}
    >
      {SENTIMENTS.map((s) => (
        <button
          key={s}
          type="button"
          onClick={() => onChange(s)}
          className={cn(
            "rounded-[7px] border border-transparent font-mono font-bold tracking-wide transition-colors",
            size === "sm" ? "px-1.5 py-0.5 text-[10px]" : "px-2.5 py-1 text-[11px]",
            value === s
              ? ACTIVE_STYLES[s]
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          {s}
        </button>
      ))}
    </div>
  )
}
