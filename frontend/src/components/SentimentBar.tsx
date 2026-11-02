/** Barra segmentada pos/neu/neg. Compartida por la barra global y el desglose
 *  por medio. Con `showLabels` escribe el % dentro de cada segmento cuando
 *  este es lo bastante ancho (≥18%), para no tener que seguir la barra con la
 *  vista hasta una leyenda aparte. */
export type SentimentBarSize = "sm" | "md"

const HEIGHT: Record<SentimentBarSize, string> = { sm: "h-2.5", md: "h-3" }

interface Props {
  positivePct: number
  neutralPct: number
  negativePct: number
  size?: SentimentBarSize
  showLabels?: boolean
  dashed?: boolean
  opacity?: number
  ariaLabel: string
}

const MIN_LABEL_PCT = 18

export function SentimentBar({
  positivePct,
  neutralPct,
  negativePct,
  size = "md",
  showLabels = true,
  dashed = false,
  opacity = 1,
  ariaLabel,
}: Props) {
  const segments = [
    { pct: positivePct, color: "var(--pos-bar)", text: "var(--pos-bar-fg)" },
    { pct: neutralPct, color: "var(--neu)", text: "var(--neu-fg)" },
    { pct: negativePct, color: "var(--neg)", text: "var(--neg-fg)" },
  ]

  return (
    <div
      className={`flex w-full overflow-hidden rounded-full ${HEIGHT[size]}`}
      style={{
        background: "var(--surface-2)",
        opacity,
        outline: dashed ? "1px dashed var(--border)" : undefined,
        outlineOffset: dashed ? 1 : undefined,
      }}
      role="img"
      aria-label={ariaLabel}
    >
      {segments.map(
        (s, i) =>
          s.pct > 0 && (
            <div
              key={i}
              className="flex items-center justify-center overflow-hidden font-mono text-[9px] font-semibold leading-none"
              style={{ width: `${s.pct}%`, background: s.color, color: s.text }}
            >
              {showLabels && s.pct >= MIN_LABEL_PCT ? `${Math.round(s.pct)}%` : null}
            </div>
          ),
      )}
    </div>
  )
}
