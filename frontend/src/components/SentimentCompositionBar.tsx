import type { SentimentAggregate } from "@/lib/sentiment-aggregate"

const DOMINANT_LABEL: Record<SentimentAggregate["dominant"], string> = {
  POS: "Mayormente positivo",
  NEG: "Mayormente negativo",
  NEU: "Mayormente neutro",
}

export function SentimentCompositionBar({ aggregate }: { aggregate: SentimentAggregate }) {
  const { positivePct, neutralPct, negativePct, dominant, lowSample, sampleSize } = aggregate

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between gap-2">
        <span
          className="text-[11.5px] font-semibold"
          style={{ color: `var(--${dominant === "POS" ? "pos" : dominant === "NEG" ? "neg" : "neu"})` }}
        >
          {DOMINANT_LABEL[dominant]}
        </span>
        {lowSample && (
          <span
            className="rounded-[5px] border px-1.5 py-0.5 text-[10px] font-medium"
            style={{ background: "var(--surface-2)", borderColor: "var(--border)", color: "var(--faint)" }}
            title={`Solo ${sampleSize} menciones — el promedio puede ser poco representativo`}
          >
            Muestra baja
          </span>
        )}
      </div>

      <div
        className="flex h-2 w-full overflow-hidden rounded-full"
        style={{ background: "var(--surface-2)" }}
        role="img"
        aria-label={`${Math.round(positivePct)}% positivo, ${Math.round(neutralPct)}% neutro, ${Math.round(negativePct)}% negativo`}
      >
        {positivePct > 0 && <div style={{ width: `${positivePct}%`, background: "var(--pos)" }} />}
        {neutralPct > 0 && <div style={{ width: `${neutralPct}%`, background: "var(--neu)" }} />}
        {negativePct > 0 && <div style={{ width: `${negativePct}%`, background: "var(--neg)" }} />}
      </div>

      <div className="flex gap-3 font-mono text-[10.5px]" style={{ color: "var(--faint)" }}>
        <span>{Math.round(positivePct)}% pos.</span>
        <span>{Math.round(neutralPct)}% neu.</span>
        <span>{Math.round(negativePct)}% neg.</span>
      </div>
    </div>
  )
}
