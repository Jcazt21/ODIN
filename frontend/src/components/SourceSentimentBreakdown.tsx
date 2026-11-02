import { useMemo, useRef, useState } from "react"
import { SentimentBar } from "@/components/SentimentBar"
import { SourceLogo } from "@/components/SourceLogo"
import { groupSentimentBySource, type SourceSentiment } from "@/lib/sentiment-by-source"
import type { CanonicalEntityArticleMention } from "@/lib/odin-api"

/** Cuántos medios se muestran siempre (los de más menciones); el resto va a «N medios más». */
const TOP_SOURCES = 5
/** Una barra más corta que esta fracción de la mayor no lleva % dentro: no cabe. */
const MIN_SHARE_FOR_LABELS = 0.2
/** Piso del largo de barra (% del ancho): un medio de 1 mención sigue siendo visible. */
const MIN_BAR_WIDTH_PCT = 4

const EASE = "cubic-bezier(0.23, 1, 0.32, 1)"

/** Trato de cada medio hacia una entidad (R3).
 *
 *  Es la misma lectura que el anillo global, partida por periódico: sirve para
 *  responder "quién habla bien y quién habla mal de este actor".
 *
 *  El largo de cada barra es proporcional a sus menciones (contra el medio más
 *  grande): una nota y veinte ya no ocupan el mismo ancho. Los colores dentro de
 *  la barra siguen mostrando el reparto, con el % escrito cuando el segmento es
 *  lo bastante ancho.
 *
 *  Se muestran los 5 medios con más menciones y el resto se agrupa en
 *  «N medios más», plegado. Un tope fijo (y no un umbral de menciones) mantiene
 *  la ficha del mismo tamaño en todas las entidades y nunca esconde lo principal
 *  de una con poco volumen. Un medio de una sola nota que entre en el top sigue
 *  marcado como muestra baja.
 *
 *  Señalar una fila (hover, foco o toque) avisa al padre qué medio es, para que
 *  el anillo muestre su lectura en lugar de la global.
 */
export function SourceSentimentBreakdown({
  articles,
  activeSource = null,
  onActiveSourceChange,
}: {
  articles: CanonicalEntityArticleMention[]
  activeSource?: string | null
  onActiveSourceChange?: (source: string | null) => void
}) {
  const rows = useMemo(() => groupSentimentBySource(articles), [articles])
  const [open, setOpen] = useState(false)
  const lastPointer = useRef<string>("mouse")
  if (rows.length === 0) return null

  const max = Math.max(...rows.map((r) => r.aggregate.sampleSize))
  // `rows` ya viene ordenado por volumen: los primeros son los mejor respaldados.
  const main = rows.slice(0, TOP_SOURCES)
  const rest = rows.slice(TOP_SOURCES)
  const restTotal = rest.reduce((sum, r) => sum + r.aggregate.sampleSize, 0)

  const renderRow = ({ source, sourceName, aggregate }: SourceSentiment, delayMs = 0) => {
    const share = aggregate.sampleSize / max
    const active = activeSource === source
    return (
      <li
        key={source}
        tabIndex={0}
        data-active={active || undefined}
        className="flex items-center gap-2.5 rounded-lg px-1.5 py-1.5 outline-none transition-colors duration-150 data-[active]:bg-[var(--surface-3)] focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
        style={{ animation: delayMs ? `odinRowIn 260ms ${EASE} ${delayMs}ms both` : undefined }}
        onPointerDown={(e) => {
          lastPointer.current = e.pointerType
        }}
        onPointerEnter={(e) => {
          if (e.pointerType === "mouse") onActiveSourceChange?.(source)
        }}
        onPointerLeave={(e) => {
          if (e.pointerType === "mouse") onActiveSourceChange?.(null)
        }}
        onFocus={() => onActiveSourceChange?.(source)}
        onBlur={() => onActiveSourceChange?.(null)}
        onClick={() => {
          if (lastPointer.current !== "mouse") onActiveSourceChange?.(active ? null : source)
        }}
      >
        <span className="flex w-[104px] min-w-0 shrink-0 flex-col gap-0.5">
          <span className="flex min-w-0 items-center gap-1.5">
            <SourceLogo source={source} className="shrink-0" />
            <span className="truncate text-[12.5px] font-medium">{sourceName}</span>
          </span>
          {aggregate.lowSample && (
            <span
              className="w-fit rounded-md border px-1.5 py-px text-[9.5px] font-medium"
              style={{ background: "var(--surface-2)", borderColor: "var(--border)", color: "var(--faint)" }}
              title={`Solo ${aggregate.sampleSize} menciones: el promedio puede no ser representativo`}
            >
              Muestra baja
            </span>
          )}
        </span>

        <div className="min-w-0 flex-1">
          <div style={{ width: `${Math.max(share * 100, MIN_BAR_WIDTH_PCT)}%` }}>
            <SentimentBar
              positivePct={aggregate.positivePct}
              neutralPct={aggregate.neutralPct}
              negativePct={aggregate.negativePct}
              size="md"
              showLabels={share >= MIN_SHARE_FOR_LABELS}
              dashed={aggregate.lowSample}
              opacity={aggregate.lowSample ? 0.7 : 1}
              ariaLabel={`${sourceName}: ${Math.round(aggregate.positivePct)}% positivo, ${Math.round(aggregate.neutralPct)}% neutro, ${Math.round(aggregate.negativePct)}% negativo, sobre ${aggregate.sampleSize} menciones`}
            />
          </div>
        </div>

        <span className="w-12 shrink-0 text-right font-mono text-[11px] tabular-nums" style={{ color: "var(--faint)" }}>
          {aggregate.sampleSize} menc.
        </span>
      </li>
    )
  }

  return (
    <div className="flex flex-col gap-1">
      <h4 className="text-[11.5px] font-semibold" style={{ color: "var(--muted-foreground)" }}>
        Trato por medio
      </h4>
      <ul className="flex flex-col">{main.map((r) => renderRow(r))}</ul>

      {rest.length > 0 && (
        <>
          <button
            type="button"
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
            className="flex items-center gap-2 rounded-lg border-t px-1.5 py-2 text-left text-[12px] transition-[background-color,transform] duration-150 active:scale-[0.98] hover:bg-[var(--surface-3)]"
            style={{ borderColor: "var(--border)", color: "var(--muted-foreground)" }}
          >
            <span
              aria-hidden
              className="inline-block transition-transform duration-200"
              style={{ transform: open ? "rotate(90deg)" : "none", transitionTimingFunction: EASE }}
            >
              ▸
            </span>
            {rest.length} {rest.length === 1 ? "medio más" : "medios más"}
            <span className="ml-auto font-mono text-[11px]" style={{ color: "var(--faint)" }}>
              {restTotal} menc.
            </span>
          </button>
          <div
            className="grid"
            style={{
              gridTemplateRows: open ? "1fr" : "0fr",
              opacity: open ? 1 : 0,
              transition: `grid-template-rows 240ms ${EASE}, opacity 200ms ease`,
            }}
            inert={!open}
          >
            <ul className="flex min-h-0 flex-col overflow-hidden">
              {rest.map((r, i) => renderRow(r, open ? i * 35 : 0))}
            </ul>
          </div>
        </>
      )}
    </div>
  )
}
