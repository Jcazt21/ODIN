import { SourceLogo } from "@/components/SourceLogo"
import { SentimentRing } from "@/components/SentimentRing"
import type { SentimentAggregate } from "@/lib/sentiment-aggregate"

const DOMINANT_WORD: Record<SentimentAggregate["dominant"], string> = {
  POS: "Positivo",
  NEG: "Negativo",
  NEU: "Neutro",
}

/** Lectura global de una entidad: anillo grande con el veredicto al centro y
 *  la leyenda en texto (no solo color). Con `scopeLabel` muestra, en cambio, la
 *  lectura de un medio concreto: lo usa el desglose al señalar una fila. */
export function SentimentCompositionBar({
  aggregate,
  scopeLabel = "Global",
  scopeSource,
}: {
  aggregate: SentimentAggregate
  scopeLabel?: string
  /** Slug del medio señalado: pone su logo junto al nombre. */
  scopeSource?: string
}) {
  const { positivePct, neutralPct, negativePct, dominant, lowSample, sampleSize } = aggregate

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        {/* Grande y con el logo del medio: es lo que avisa que el anillo ya no
            es el global sino el de ese medio. Altura fija para que no salte. */}
        <span className="flex min-h-7 min-w-0 items-center gap-2 text-[17px] font-semibold leading-none">
          {scopeSource && <SourceLogo source={scopeSource} className="size-6 shrink-0" />}
          <span className="truncate">{scopeLabel}</span>
        </span>
        {lowSample && (
          <span
            className="inline-block shrink-0 rounded-md border px-1.5 py-0.5 text-[10px] font-medium"
            style={{ background: "var(--surface-2)", borderColor: "var(--border)", color: "var(--faint)" }}
            title={`Solo ${sampleSize} menciones — el promedio puede ser poco representativo`}
          >
            Muestra baja
          </span>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
        <SentimentRing
          className="size-44 shrink-0 sm:size-52"
          positivePct={positivePct}
          neutralPct={neutralPct}
          negativePct={negativePct}
          verdict={DOMINANT_WORD[dominant]}
          caption={`${sampleSize} menc.`}
        />
        <div className="flex flex-col gap-1.5 text-[13px]" style={{ color: "var(--muted-foreground)" }}>
          {[
            { pct: positivePct, label: "positivo", color: "var(--pos-bar)" },
            { pct: neutralPct, label: "neutro", color: "var(--neu)" },
            { pct: negativePct, label: "negativo", color: "var(--neg)" },
          ].map((l) => (
            <span key={l.label} className="inline-flex items-center gap-1.5">
              <span aria-hidden className="inline-block size-1.5 rounded-full" style={{ background: l.color }} />
              {`${Math.round(l.pct)}% ${l.label}`}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}
