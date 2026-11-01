import { Link } from "react-router-dom"
import { Alert } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { SentimentDot } from "@/components/reports/SentimentDot"
import { formatDateShort } from "@/lib/format"
import type { ArticleSummary } from "@/lib/odin-api"

interface ArticleRowsListProps {
  articles: ArticleSummary[]
  /** Total en el servidor; si supera lo mostrado aparece «Cargar más». */
  total: number
  loading?: boolean
  loadingMore?: boolean
  error?: boolean
  onLoadMore?: () => void
}

/** Artículos de una fila expandida (autor o tema). */
export function ArticleRowsList({ articles, total, loading, loadingMore, error, onLoadMore }: ArticleRowsListProps) {
  if (error) return <Alert variant="destructive">No se pudieron cargar los artículos.</Alert>
  if (loading) {
    return (
      <div role="status" aria-label="Cargando artículos" className="space-y-2">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-5 w-full" />
        ))}
      </div>
    )
  }
  if (articles.length === 0) return <p className="text-sm text-muted-foreground">No hay artículos.</p>

  return (
    <div className="space-y-2">
      <ul className="divide-y">
        {articles.map((a) => (
          <li key={a.id} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 py-2 text-sm">
            <Link to={`/reports/${a.id}`} className="min-w-0 flex-1 font-medium hover:underline">
              {a.title}
            </Link>
            <span className="flex shrink-0 items-center gap-3 text-xs text-muted-foreground">
              <span>{formatDateShort(a.published_at)}</span>
              <SentimentDot sentiment={a.overall_sentiment ?? null} />
            </span>
          </li>
        ))}
      </ul>
      {total > articles.length && onLoadMore && (
        <Button type="button" variant="outline" size="sm" disabled={loadingMore} onClick={onLoadMore}>
          {loadingMore ? "Cargando…" : "Cargar más"}
        </Button>
      )}
    </div>
  )
}
