import { useMemo, useState } from "react"
import { Search } from "lucide-react"
import { ArticleRowsList } from "@/components/ArticleRowsList"
import { ExpandableRow } from "@/components/ExpandableRow"
import { PageHeader } from "@/components/PageHeader"
import { Alert } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { useTopicArticles, useTopicTree } from "@/lib/queries/topics"
import { flattenTopicTree, normalizeText } from "@/lib/topic-tree"

const COLUMNS = 3
const CELL = "px-3.5 py-3 align-middle"
const HEADER = "border-b px-3.5 py-2.5 text-left text-xs font-medium whitespace-nowrap text-muted-foreground"
const INDENT_REM = 1.25

function TopicArticles({ id }: { id: number }) {
  const [limit, setLimit] = useState(10)
  const query = useTopicArticles(id, true, limit)
  return (
    <ArticleRowsList
      articles={query.data?.items ?? []}
      total={query.data?.total ?? 0}
      loading={query.isPending}
      loadingMore={query.isFetching && !query.isPending}
      error={query.isError}
      onLoadMore={() => setLimit((l) => l + 10)}
    />
  )
}

export function TopicsPage() {
  const [search, setSearch] = useState("")
  const [includeInactive, setIncludeInactive] = useState(false)
  const { data, isLoading, error } = useTopicTree({ include_inactive: includeInactive })

  const rows = useMemo(() => {
    const flat = flattenTopicTree(data ?? [])
    const needle = normalizeText(search)
    return needle ? flat.filter((r) => normalizeText(r.name).includes(needle)) : flat
  }, [data, search])

  return (
    <div className="flex w-full flex-col gap-4">
      <PageHeader title="Temas" count={data ? `${rows.length} ${rows.length === 1 ? "tema" : "temas"}` : undefined} />

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-[220px] flex-1">
          <Search aria-hidden className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-[var(--faint)]" />
          <input
            aria-label="Buscar temas"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Nombre del tema…"
            className="h-9 w-full rounded-lg border bg-[var(--surface)] px-2.5 pl-8 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        </div>
        <label className="inline-flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={includeInactive}
            onChange={(e) => setIncludeInactive(e.target.checked)}
            className="size-4 accent-[var(--primary)]"
          />
          Incluir inactivos
        </label>
      </div>

      {error ? (
        <Alert variant="destructive">No se pudieron cargar los temas.</Alert>
      ) : (
        <div className="overflow-x-auto rounded-xl border bg-card">
          <table className="w-full text-sm">
            <thead>
              <tr>
                <th className={`${HEADER} w-10`}>
                  <span className="sr-only">Artículos</span>
                </th>
                <th className={HEADER}>Tema</th>
                <th className={HEADER}>Artículos</th>
              </tr>
            </thead>
            {isLoading ? (
              <tbody role="status" aria-label="Cargando temas">
                {Array.from({ length: 6 }, (_, i) => (
                  <tr key={i} className="border-b">
                    <td colSpan={COLUMNS} className={CELL}>
                      <Skeleton className="h-5 w-full" />
                    </td>
                  </tr>
                ))}
              </tbody>
            ) : rows.length === 0 ? (
              <tbody>
                <tr>
                  <td colSpan={COLUMNS} className="px-4 py-10 text-center text-muted-foreground">
                    No hay temas que coincidan.
                  </td>
                </tr>
              </tbody>
            ) : (
              <tbody>
                {rows.map((t) => (
                  <ExpandableRow
                    key={t.id}
                    label={t.name}
                    colSpan={COLUMNS}
                    cells={
                      <>
                        <td className={CELL}>
                          <span
                            data-depth={t.depth}
                            style={{ paddingLeft: `${t.depth * INDENT_REM}rem` }}
                            className={t.depth === 0 ? "font-medium" : undefined}
                          >
                            {t.name}
                          </span>
                        </td>
                        <td className={CELL}>
                          <Badge variant="secondary" className="tabular-nums">{t.article_count}</Badge>
                        </td>
                      </>
                    }
                  >
                    <TopicArticles id={t.id} />
                  </ExpandableRow>
                ))}
              </tbody>
            )}
          </table>
        </div>
      )}
    </div>
  )
}
