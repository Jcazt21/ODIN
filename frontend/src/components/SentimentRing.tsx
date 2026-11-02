/** Anillo de sentimiento pos/neu/neg con el veredicto al centro.
 *
 *  Los tres arcos se dibujan siempre (los de 0% con largo 0) para que, al
 *  cambiar de medio, el largo y la posición de cada uno transicionen en vez de
 *  aparecer o desaparecer de golpe. La transición es corta y con ease-out:
 *  responde a un hover, que ocurre decenas de veces por sesión. */
interface Props {
  positivePct: number
  neutralPct: number
  negativePct: number
  /** Texto grande al centro (veredicto). */
  verdict: string
  /** Texto pequeño bajo el veredicto (volumen). */
  caption: string
  className?: string
}

const CIRCUMFERENCE = 100 // r = 100 / 2π ≈ 15.9
const GAP = 1.2 // aire entre arcos contiguos
const START = 25 // arranca a las 12 en punto

const ARCS = [
  { key: "pos", color: "var(--pos-bar)", label: "positivo" },
  { key: "neu", color: "var(--neu)", label: "neutro" },
  { key: "neg", color: "var(--neg)", label: "negativo" },
] as const

export function SentimentRing({ positivePct, neutralPct, negativePct, verdict, caption, className }: Props) {
  const values = [positivePct, neutralPct, negativePct]
  let acc = 0
  const arcs = ARCS.map((arc, i) => {
    const pct = values[i]
    const length = pct > 0 ? Math.max(0, pct - GAP) : 0
    const offset = START - acc
    acc += pct
    return { ...arc, pct, length, offset }
  })

  const ariaLabel = `${verdict}: ${arcs.map((a) => `${Math.round(a.pct)}% ${a.label}`).join(", ")}`

  return (
    <svg viewBox="0 0 42 42" role="img" aria-label={ariaLabel} className={className}>
      {arcs.map((a) => (
        <circle
          key={a.key}
          data-arc={a.pct > 0 ? a.key : undefined}
          cx="21"
          cy="21"
          r="15.9"
          fill="none"
          stroke={a.color}
          strokeWidth="4"
          style={{
            strokeDasharray: `${a.length} ${CIRCUMFERENCE - a.length}`,
            strokeDashoffset: a.offset,
            transition:
              "stroke-dasharray 240ms cubic-bezier(0.23, 1, 0.32, 1), stroke-dashoffset 240ms cubic-bezier(0.23, 1, 0.32, 1)",
          }}
          className="motion-reduce:!transition-none"
        />
      ))}
      <text x="21" y="21" textAnchor="middle" fontSize="5" fontWeight="600" fill="currentColor">
        {verdict}
      </text>
      <text x="21" y="26.5" textAnchor="middle" fontSize="3.2" fill="var(--faint)">
        {caption}
      </text>
    </svg>
  )
}
