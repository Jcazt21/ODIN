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

export interface AnalysisCardFields {
  title: string
  url: string
  source: string
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

const WEIGHT_BY_FIELD: Record<string, number> = {
  framing: 82,
  headline_intent: 64,
  lead_orientation: 55,
  source_quality: 48,
}

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

  return (
    <div
      className="odin-glass overflow-hidden rounded-xl border"
      style={{ boxShadow: "var(--shadow-sm)" }}
    >
      {/* 1. Cabecera */}
      <div className="space-y-3 px-6 py-[22px]">
        <div className="flex flex-wrap items-center gap-2">
          {editable ? (
            <SentimentSegmented
              value={(value.overall_sentiment as "POS" | "NEG" | "NEU" | null) ?? "NEU"}
              onChange={(v) => patch({ overall_sentiment: v })}
            />
          ) : (
            <SentimentBadge sentiment={value.overall_sentiment} score={value.sentiment_score} />
          )}
        </div>
        <h1
          className="text-[22px] leading-[1.3] font-semibold text-pretty"
          style={{ letterSpacing: "-0.015em", maxWidth: "52ch" }}
        >
          <a href={value.url} target="_blank" rel="noreferrer" className="hover:underline">
            {value.title}
          </a>
        </h1>
        <div className="flex flex-wrap items-center gap-x-[18px] gap-y-1 text-[12.5px]">
          <span>
            <span style={{ color: "var(--faint)" }}>Fuente </span>
            <span style={{ color: "var(--muted-foreground)" }}>{value.source}</span>
          </span>
          {value.authors && (
            <span>
              <span style={{ color: "var(--faint)" }}>Autor </span>
              <span style={{ color: "var(--muted-foreground)" }}>{value.authors}</span>
            </span>
          )}
          {value.section && (
            <span>
              <span style={{ color: "var(--faint)" }}>Sección </span>
              <span style={{ color: "var(--muted-foreground)" }}>{value.section}</span>
            </span>
          )}
          <span>
            <span style={{ color: "var(--faint)" }}>Publicado </span>
            <span style={{ color: "var(--muted-foreground)" }}>{formatDateFull(value.published_at)}</span>
          </span>
          <a href={value.url} target="_blank" rel="noreferrer" className="font-mono hover:underline">
            ver original ↗
          </a>
        </div>
      </div>

      {/* 2. Tema y palabras clave */}
      <div className="grid gap-5 border-t px-6 py-[22px] sm:grid-cols-2" style={{ borderColor: "var(--border)" }}>
        <div className="space-y-1.5">
          <p className="font-mono text-[10.5px] font-medium tracking-[0.12em] uppercase" style={{ color: "var(--faint)" }}>
            Tema principal
          </p>
          {editable ? (
            <input
              value={value.main_topic ?? ""}
              onChange={(e) => patch({ main_topic: e.target.value || null })}
              className="h-8 w-full rounded-[7px] border border-dashed bg-transparent px-2 text-[13.5px] font-medium outline-none"
              style={{ borderColor: "var(--border-strong)" }}
            />
          ) : (
            <p className="text-[13.5px] font-medium capitalize">{value.main_topic ?? "—"}</p>
          )}
        </div>
        <div className="space-y-1.5">
          <p className="font-mono text-[10.5px] font-medium tracking-[0.12em] uppercase" style={{ color: "var(--faint)" }}>
            Palabras clave
          </p>
          {editable ? (
            <input
              value={value.topic_keywords ?? ""}
              onChange={(e) => patch({ topic_keywords: e.target.value || null })}
              className="h-8 w-full rounded-[7px] border border-dashed bg-transparent px-2 text-[13.5px] outline-none"
              style={{ borderColor: "var(--border-strong)" }}
            />
          ) : keywords.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {keywords.map((kw) => (
                <span
                  key={kw}
                  className="rounded-[5px] border px-2 py-0.5 text-[11.5px]"
                  style={{ background: "var(--surface-2)", borderColor: "var(--border)", color: "var(--muted-foreground)" }}
                >
                  {kw}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-[13.5px]" style={{ color: "var(--faint)" }}>—</p>
          )}
        </div>
      </div>

      {/* 3. Análisis de encuadre */}
      {(editable || value.framing != null) && (
        <div className="border-t px-6 py-[22px]" style={{ borderColor: "var(--border)" }}>
          <p className="mb-1 font-mono text-[10.5px] font-medium tracking-[0.12em] uppercase" style={{ color: "var(--faint)" }}>
            Análisis de encuadre
          </p>
          <p className="mb-3 text-[12.5px]" style={{ color: "var(--muted-foreground)" }}>
            Cómo el medio construye la historia
          </p>
          <div className="grid gap-3" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))" }}>
            {FRAMING_FIELDS.map(([label, field, labels]) => {
              const raw = value[field]
              const tone = toneVars(toneOf(raw))
              const weight = WEIGHT_BY_FIELD[field] ?? 60
              return (
                <div
                  key={field}
                  className="space-y-2 rounded-[9px] border p-3"
                  style={{ background: tone.bg, borderColor: tone.border }}
                >
                  <p className="text-[11px] font-semibold tracking-[0.06em] uppercase" style={{ color: "var(--faint)" }}>
                    {label}
                  </p>
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
                    <p className="text-[15px] leading-[1.25] font-semibold" style={{ color: tone.color }}>
                      {raw ? (labels as Record<string, string>)[raw] ?? raw : "—"}
                    </p>
                  )}
                  <div className="h-[3px] overflow-hidden rounded-full" style={{ background: "var(--border)" }}>
                    <div className="h-full rounded-full" style={{ width: `${weight}%`, background: tone.color }} />
                  </div>
                </div>
              )
            })}
          </div>

          {/* 4. Actores */}
          <div className="mt-3 grid items-end gap-3" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))" }}>
            {ACTOR_FIELDS.map(([label, field]) => (
              <div key={field} className="space-y-1">
                <p className="text-[11px] font-medium" style={{ color: "var(--faint)" }}>
                  {label}
                </p>
                {editable ? (
                  <input
                    value={value[field] ?? ""}
                    onChange={(e) => patch({ [field]: e.target.value || null } as Partial<AnalysisCardFields>)}
                    className="h-8 w-full rounded-[7px] border border-dashed bg-transparent px-2 text-[13px] font-medium outline-none"
                    style={{ borderColor: "var(--border-strong)" }}
                  />
                ) : (
                  <p className="text-[13px] font-medium">{value[field] ?? "—"}</p>
                )}
              </div>
            ))}
            <div className="space-y-1">
              <p className="text-[11px] font-medium" style={{ color: "var(--faint)" }}>
                Datos duros
              </p>
              {(() => {
                const hard = value.has_hard_data
                const tone = toneVars(hard == null ? "neu" : hard ? "pos" : "neu")
                return (
                  <span
                    className="inline-block rounded-[5px] border px-2 py-0.5 text-[11.5px] font-semibold"
                    style={{ background: tone.bg, borderColor: tone.border, color: tone.color }}
                  >
                    {hard == null ? "—" : hard ? "Sí" : "No"}
                  </span>
                )
              })()}
            </div>
          </div>
        </div>
      )}

      {/* 5. Cuerpo del artículo */}
      <div className="border-t px-6 py-[22px]" style={{ borderColor: "var(--border)" }}>
        <p className="mb-1.5 font-mono text-[10.5px] font-medium tracking-[0.12em] uppercase" style={{ color: "var(--faint)" }}>
          Cuerpo del artículo
        </p>
        <div
          className="max-h-[230px] overflow-auto rounded-[9px] border px-[18px] py-4 text-[13.5px] leading-[1.7]"
          style={{ background: "var(--surface-2)", borderColor: "var(--border)", color: "var(--muted-foreground)" }}
        >
          {(value.body ?? "")
            .split(/\n+/)
            .map((p) => p.trim())
            .filter(Boolean)
            .map((p, i) => (
              <p key={i} className="text-pretty" style={{ marginBottom: "12px" }}>
                {p}
              </p>
            ))}
        </div>
      </div>
    </div>
  )
}
