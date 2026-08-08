import { ChevronLeft, ChevronRight } from "lucide-react"
import { SentimentBadge } from "@/components/SentimentBadge"
import { FRAMING_LABELS } from "@/lib/labels"
import { formatDateShort } from "@/lib/format"
import type { ArticleSummary } from "@/lib/odin-api"

export function ReportsTable({
  items,
  loading,
  onOpen,
  sortDir,
  onToggleSort,
}: {
  items: ArticleSummary[]
  loading: boolean
  onOpen: (id: number) => void
  sortDir: "recent" | "oldest"
  onToggleSort: () => void
}) {
  return (
    <div
      className="odin-glass overflow-hidden rounded-xl border"
    >
      <table className="w-full border-collapse text-[13px]">
        <thead>
          <tr style={{ background: "var(--surface-2)" }}>
            <th
              onClick={onToggleSort}
              className="cursor-pointer border-b px-[14px] py-[10px] text-left font-mono text-[10.5px] font-medium tracking-[0.1em] uppercase whitespace-nowrap select-none"
              style={{ borderColor: "var(--border)", color: "var(--primary)" }}
            >
              Fecha {sortDir === "recent" ? "↓" : "↑"}
            </th>
            {["Artículo", "Fuente", "Sentimiento", "Encuadre"].map((h) => (
              <th
                key={h}
                className="border-b px-[14px] py-[10px] text-left font-mono text-[10.5px] font-medium tracking-[0.1em] uppercase whitespace-nowrap"
                style={{ borderColor: "var(--border)", color: "var(--faint)" }}
              >
                {h}
              </th>
            ))}
            <th
              className="border-b px-[14px] py-[10px] text-right font-mono text-[10.5px] font-medium tracking-[0.1em] uppercase whitespace-nowrap"
              style={{ borderColor: "var(--border)", color: "var(--faint)" }}
            >
              Ent.
            </th>
            <th
              className="border-b px-[14px] py-[10px] text-center font-mono text-[10.5px] font-medium tracking-[0.1em] uppercase whitespace-nowrap"
              style={{ borderColor: "var(--border)", color: "var(--faint)" }}
            >
              Datos
            </th>
          </tr>
        </thead>
        <tbody>
          {loading
            ? Array.from({ length: 6 }).map((_, i) => (
                <tr key={i} className="border-b" style={{ borderColor: "var(--border)" }}>
                  <td className="px-[14px] py-3" colSpan={7}>
                    <div
                      className="h-4 rounded"
                      style={{ background: "var(--surface-3)", animation: "odinPulse 1.6s ease-in-out infinite" }}
                    />
                  </td>
                </tr>
              ))
            : items.map((a) => (
                <tr
                  key={a.id}
                  onClick={() => onOpen(a.id)}
                  className="cursor-pointer border-b transition-colors"
                  style={{ borderColor: "var(--border)" }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surface-2)")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                >
                  <td className="px-[14px] py-3 align-top font-mono text-[11.5px] whitespace-nowrap" style={{ color: "var(--faint)" }}>
                    {formatDateShort(a.published_at)}
                  </td>
                  <td className="max-w-[380px] px-[14px] py-3 align-top">
                    <p className="font-medium leading-[1.4]">{a.title}</p>
                    {a.main_topic && (
                      <p className="mt-0.5 text-[12px] capitalize" style={{ color: "var(--muted-foreground)" }}>
                        {a.main_topic}
                      </p>
                    )}
                  </td>
                  <td className="px-[14px] py-3 align-top" style={{ color: "var(--muted-foreground)" }}>
                    {a.source}
                  </td>
                  <td className="px-[14px] py-3 align-top">
                    <SentimentBadge sentiment={a.overall_sentiment} score={a.sentiment_score} />
                  </td>
                  <td className="px-[14px] py-3 align-top">
                    {a.framing ? (
                      <span
                        className="rounded-[5px] border px-2 py-0.5 text-[11.5px]"
                        style={{ background: "var(--surface-2)", borderColor: "var(--border)", color: "var(--muted-foreground)" }}
                      >
                        {FRAMING_LABELS[a.framing] ?? a.framing}
                      </span>
                    ) : (
                      <span style={{ color: "var(--faint)" }}>—</span>
                    )}
                  </td>
                  <td className="px-[14px] py-3 text-right align-top font-mono" style={{ color: "var(--muted-foreground)" }}>
                    {a.entity_count}
                  </td>
                  <td className="px-[14px] py-3 text-center align-top">
                    {a.has_hard_data ? (
                      <span style={{ color: "var(--primary)" }}>●</span>
                    ) : (
                      <span style={{ color: "var(--faint)" }}>—</span>
                    )}
                  </td>
                </tr>
              ))}
        </tbody>
      </table>
    </div>
  )
}

export function Pagination({
  page,
  total,
  pageSize,
  loaded,
  loading,
  onPrev,
  onNext,
}: {
  page: number
  total: number
  pageSize: number
  loaded: number
  loading: boolean
  onPrev: () => void
  onNext: () => void
}) {
  const to = Math.min(total, (page + 1) * pageSize)
  if (total <= pageSize) return null
  return (
    <div
      className="flex items-center justify-between rounded-xl border px-[14px] py-[11px]"
      style={{ background: "var(--surface-2)", borderColor: "var(--border)" }}
    >
      <span className="text-[12px]" style={{ color: "var(--faint)" }}>
        Página {page + 1} de {Math.max(1, Math.ceil(total / pageSize))} · {loaded} visibles
      </span>
      <div className="flex items-center gap-2">
        <button
          type="button"
          disabled={page === 0 || loading}
          onClick={onPrev}
          className="inline-flex items-center gap-1 rounded-[6px] border px-2.5 py-1 text-[12.5px] disabled:opacity-50"
          style={{ background: "var(--surface)", borderColor: "var(--border)" }}
        >
          <ChevronLeft className="size-3.5" />
          Anterior
        </button>
        <button
          type="button"
          disabled={to >= total || loading}
          onClick={onNext}
          className="inline-flex items-center gap-1 rounded-[6px] border px-2.5 py-1 text-[12.5px] disabled:opacity-50"
          style={{ background: "var(--surface)", borderColor: "var(--border)" }}
        >
          Siguiente
          <ChevronRight className="size-3.5" />
        </button>
      </div>
    </div>
  )
}
