import { useMemo } from "react"
import { groupSentimentBySource } from "@/lib/sentiment-by-source"
import type { CanonicalEntityArticleMention } from "@/lib/odin-api"

/** Trato de cada medio hacia una entidad (R3).
 *
 *  Es la misma lectura que la barra global, partida por periódico: sirve para
 *  responder "quién habla bien y quién habla mal de este actor".
 *
 *  Los medios con pocas menciones se muestran, pero marcados: con este volumen
 *  de datos la mayoría se apoya en una sola nota, y un "100% negativo" de un
 *  artículo al lado de un promedio de veintiocho se lee como si valieran lo
 *  mismo. El volumen va siempre a la vista por el mismo motivo.
 */
export function SourceSentimentBreakdown({
  articles,
}: {
  articles: CanonicalEntityArticleMention[]
}) {
  const rows = useMemo(() => groupSentimentBySource(articles), [articles])
  if (rows.length === 0) return null

  return (
    <div className="flex flex-col gap-2">
      <h4 className="text-[11.5px] font-semibold" style={{ color: "var(--muted-foreground)" }}>
        Trato por medio
      </h4>
      <ul className="flex flex-col gap-2">
        {rows.map(({ source, sourceName, aggregate }) => (
          <li key={source} className="flex flex-col gap-1">
            <div className="flex items-baseline justify-between gap-2">
              <span className="flex items-baseline gap-2">
                <span className="text-[12.5px] font-medium">{sourceName}</span>
                {aggregate.lowSample && (
                  <span
                    className="inline-block rounded-[5px] border px-1.5 py-0.5 text-[10px] font-medium"
                    style={{
                      background: "var(--surface-2)",
                      borderColor: "var(--border)",
                      color: "var(--faint)",
                    }}
                    title={`Solo ${aggregate.sampleSize} menciones: el promedio puede no ser representativo`}
                  >
                    Muestra baja
                  </span>
                )}
              </span>
              <span className="font-mono text-[11px]" style={{ color: "var(--faint)" }}>
                {aggregate.sampleSize} menc.
              </span>
            </div>

            {/* Atenuada cuando la muestra es baja: la barra sigue ahí, pero no
                compite visualmente con las que sí tienen respaldo. */}
            <div
              className="flex h-1.5 overflow-hidden rounded-full"
              style={{ background: "var(--surface-2)", opacity: aggregate.lowSample ? 0.45 : 1 }}
              role="img"
              aria-label={`${sourceName}: ${Math.round(aggregate.positivePct)}% positivo, ${Math.round(aggregate.neutralPct)}% neutro, ${Math.round(aggregate.negativePct)}% negativo, sobre ${aggregate.sampleSize} menciones`}
            >
              <div style={{ width: `${aggregate.positivePct}%`, background: "var(--pos)" }} />
              <div style={{ width: `${aggregate.neutralPct}%`, background: "var(--neu)" }} />
              <div style={{ width: `${aggregate.negativePct}%`, background: "var(--neg)" }} />
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
