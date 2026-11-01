import type * as React from "react"
import { Select } from "@/components/ui/select"
import { SentimentBadge } from "@/components/SentimentBadge"
import { SentimentSegmented } from "@/components/SentimentSegmented"
import {
  FRAMING_LABELS,
  HEADLINE_LABELS,
  LEAD_LABELS,
  SOURCE_LABELS,
  toneOf,
  toneVars,
} from "@/lib/labels"
import { formatDateFull } from "@/lib/format"
import { cn } from "@/lib/utils"

export interface AnalysisCardFields {
  title: string
  url: string
  source: string
  /** Nombre legible del medio; el backend lo deriva del slug. */
  source_name?: string
  /** Documentalista que dejó guardado el reporte. Opcional a propósito: la
   *  vista previa de /api/analyze (AnalyzePage) todavía no tiene reporte
   *  guardado, así que no manda el campo y la línea no se dibuja. En un
   *  reporte guardado sí llega, y `null` significa rastreo automático. */
  documentalist?: string | null
  authors: string | null
  section: string | null
  published_at: string | null
  body: string | null
  main_topic: string | null
  topic_keywords: string | null
  overall_sentiment: string | null
  sentiment_score: number | null
  // Los 4 campos de encuadre: el schema del backend los declara `string`
  // (columnas ORM sin CHECK constraint), no el enum estrecho — se acepta
  // aquí igual de ancho para que tanto ArticleAnalysis como
  // SaveArticlePayload encajen sin cast en el llamador.
  framing: string | null
  headline_intent: string | null
  lead_orientation: string | null
  source_quality: string | null
  has_hard_data: boolean | null
  dominant_actor: string | null
  blamed_actor: string | null
  credited_actor: string | null
}

const FRAMING_FIELDS = [
  ["Marco narrativo", "framing", FRAMING_LABELS] as const,
  ["Intención del titular", "headline_intent", HEADLINE_LABELS] as const,
  ["Orientación del lead", "lead_orientation", LEAD_LABELS] as const,
  ["Calidad de fuentes", "source_quality", SOURCE_LABELS] as const,
]

const ACTOR_FIELDS = [
  ["Actor dominante", "dominant_actor"] as const,
  ["Actor señalado", "blamed_actor"] as const,
  ["Actor acreditado", "credited_actor"] as const,
]

export function AnalysisCard({
  value,
  editable,
  onChange,
}: {
  value: AnalysisCardFields
  editable: boolean
  onChange?: (patch: Partial<AnalysisCardFields>) => void
}) {
  function patch(p: Partial<AnalysisCardFields>) {
    onChange?.(p)
  }

  const keywords = (value.topic_keywords ?? "")
    .split(",")
    .map((k) => k.trim())
    .filter(Boolean)

  const hasAnalysis =
    editable ||
    [
      value.framing,
      value.headline_intent,
      value.lead_orientation,
      value.source_quality,
      value.has_hard_data,
      value.dominant_actor,
      value.blamed_actor,
      value.credited_actor,
    ].some((v) => v != null)

  const label = "text-xs font-medium text-muted-foreground"
  const tile = "space-y-1.5 rounded-xl border bg-[var(--surface)] p-4 shadow-[var(--shadow-sm)]"
  const editInput =
    "h-9 w-full rounded-lg border border-dashed bg-transparent px-2.5 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
  const meta = (name: string, content: React.ReactNode) => (
    <span>
      <span className="text-[var(--faint)]">{name} </span>
      <span className="text-muted-foreground">{content}</span>
    </span>
  )

  return (
    <article className="flex flex-col gap-6">
      {/* 1. Sentimiento, título y datos de la nota */}
      <header className="space-y-3">
        {editable ? (
          <SentimentSegmented
            value={(value.overall_sentiment as "POS" | "NEG" | "NEU" | null) ?? "NEU"}
            onChange={(v) => patch({ overall_sentiment: v })}
          />
        ) : (
          <SentimentBadge sentiment={value.overall_sentiment} score={value.sentiment_score} />
        )}
        <h2 className="max-w-[52ch] text-2xl leading-tight font-semibold tracking-tight text-pretty">
          <a href={value.url} target="_blank" rel="noreferrer" className="hover:underline">
            {value.title}
          </a>
        </h2>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
          {/* Mismo fallback que la columna de la tabla de reportes: sin
              documentalista es que lo trajo el rastreo, no que falte el dato. */}
          {value.documentalist !== undefined && meta("Documentalista", value.documentalist ?? "Automático")}
          {/* El nombre legible, no el slug: "Listín Diario" y no listin_diario. */}
          {meta("Fuente", value.source_name || value.source)}
          {editable ? (
            <label className="flex items-center gap-1.5">
              <span className="text-[var(--faint)]">Autor</span>
              <input
                value={value.authors ?? ""}
                onChange={(e) => patch({ authors: e.target.value || null })}
                className={cn(editInput, "h-8 w-56")}
              />
            </label>
          ) : (
            value.authors && meta("Autor", value.authors)
          )}
          {value.section && meta("Sección", value.section)}
          {meta("Publicado", formatDateFull(value.published_at))}
          <a href={value.url} target="_blank" rel="noreferrer" className="font-mono text-xs text-muted-foreground hover:underline">
            ver original ↗
          </a>
        </div>
      </header>

      {/* 2. Tema y palabras clave */}
      <section className="grid gap-5 border-t pt-6 sm:grid-cols-2">
        <div className="space-y-1.5">
          <p className={label}>Tema principal</p>
          {editable ? (
            <input
              value={value.main_topic ?? ""}
              onChange={(e) => patch({ main_topic: e.target.value || null })}
              className={editInput}
            />
          ) : (
            <p className={cn("text-[15px] font-medium capitalize", !value.main_topic && "text-[var(--faint)]")}>
              {value.main_topic ?? "—"}
            </p>
          )}
        </div>
        <div className="space-y-1.5">
          <p className={label}>Palabras clave</p>
          {editable ? (
            <input
              value={value.topic_keywords ?? ""}
              onChange={(e) => patch({ topic_keywords: e.target.value || null })}
              className={editInput}
            />
          ) : keywords.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {keywords.map((kw) => (
                <span key={kw} className="rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                  {kw}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-sm text-[var(--faint)]">—</p>
          )}
        </div>
      </section>

      {/* 3. Resultado de un vistazo: una ficha por dato clave */}
      {hasAnalysis && (
        <section className="space-y-4 border-t pt-6">
          <ul
            aria-label="Resultado del análisis"
            className="grid grid-cols-2 gap-3 lg:grid-cols-3 2xl:grid-cols-5"
          >
            {FRAMING_FIELDS.map(([name, field, labels]) => {
              const raw = value[field]
              const tone = toneVars(toneOf(raw))
              return (
                <li key={field} className={tile}>
                  <p className={label}>{name}</p>
                  {editable ? (
                    <Select
                      dashed
                      value={raw ?? ""}
                      onChange={(e) => patch({ [field]: e.target.value || null } as Partial<AnalysisCardFields>)}
                    >
                      <option value="">—</option>
                      {Object.entries(labels).map(([v, l]) => (
                        <option key={v} value={v}>
                          {l}
                        </option>
                      ))}
                    </Select>
                  ) : (
                    <p
                      className={cn("text-lg leading-snug font-semibold", !raw && "text-[var(--faint)]")}
                      style={raw ? { color: tone.color } : undefined}
                    >
                      {raw ? ((labels as Record<string, string>)[raw] ?? raw) : "—"}
                    </p>
                  )}
                </li>
              )
            })}
            <li className={tile}>
              <p className={label}>Datos duros</p>
              <p
                className={cn(
                  "text-lg leading-snug font-semibold",
                  value.has_hard_data == null && "text-[var(--faint)]"
                )}
              >
                {value.has_hard_data == null ? "—" : value.has_hard_data ? "Sí" : "No"}
              </p>
            </li>
          </ul>

          <div className="grid gap-3 sm:grid-cols-3">
            {ACTOR_FIELDS.map(([name, field]) => (
              <div key={field} className="space-y-1">
                <p className={label}>{name}</p>
                {editable ? (
                  <input
                    value={value[field] ?? ""}
                    onChange={(e) => patch({ [field]: e.target.value || null } as Partial<AnalysisCardFields>)}
                    className={editInput}
                  />
                ) : value[field] ? (
                  <p className="text-[15px] font-medium">{value[field]}</p>
                ) : (
                  <p className="text-[15px] text-[var(--faint)]">—</p>
                )}
              </div>
            ))}
          </div>
        </section>
      )}
    </article>
  )
}
