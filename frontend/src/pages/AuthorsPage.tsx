import { useMemo, useState } from "react"
import { Search } from "lucide-react"
import { ArticleRowsList } from "@/components/ArticleRowsList"
import { ExpandableRow } from "@/components/ExpandableRow"
import { PageHeader } from "@/components/PageHeader"
import { Alert } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Select } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { useAuthorArticles, useAuthors } from "@/lib/queries/authors"
import { useSources } from "@/lib/queries/sources"
import { useDebouncedTextFilters } from "@/lib/use-debounced-text-filters"
import { formatDateShort } from "@/lib/format"
import type { AuthorListParams } from "@/lib/odin-api"

const PAGE = 50
const COLUMNS = 5
const CELL = "px-3.5 py-3 align-middle"
const HEADER = "border-b px-3.5 py-2.5 text-left text-xs font-medium whitespace-nowrap text-muted-foreground"
const SKELETON_ROWS = 6

function AuthorArticles({ name }: { name: string }) {
  const [limit, setLimit] = useState(10)
  const query = useAuthorArticles(name, true, limit)
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

export function AuthorsPage() {
  const [search, setSearch] = useState("")
  const [source, setSource] = useState("")
  const [sort, setSort] = useState<"articles" | "name">("articles")
  const [limit, setLimit] = useState(PAGE)
  // Memoizado: el hook compara por identidad y un objeto nuevo en cada render lo haría ciclar.
  const textFilters = useMemo(() => ({ q: search || undefined }), [search])
  const { q } = useDebouncedTextFilters(textFilters)
  const { data: sources } = useSources()

  const params: AuthorListParams = { q, source: source || undefined, sort, limit }
  const { data, isLoading, error } = useAuthors(params)

  const sourceLabels = useMemo(() => new Map((sources ?? []).map((s) => [s.value, s.label])), [sources])
  const items = data?.items ?? []
  const total = data?.total ?? 0

  return (
    <div className="flex w-full flex-col gap-4">
      <PageHeader title="Autores" count={data ? `${total} ${total === 1 ? "autor" : "autores"}` : undefined} />

      <div className="flex flex-wrap items-start gap-2">
        <div className="relative min-w-[220px] flex-1">
          <Search aria-hidden className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-[var(--faint)]" />
          <input
            aria-label="Buscar autores"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Nombre del autor…"
            className="h-9 w-full rounded-lg border bg-[var(--surface)] px-2.5 pl-8 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        </div>
        <Select aria-label="Fuente" className="w-44" value={source} onChange={(e) => setSource(e.target.value)}>
          <option value="">Todas las fuentes</option>
          {(sources ?? []).map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </Select>
        <Select
          aria-label="Ordenar por"
          className="w-44"
          value={sort}
          onChange={(e) => setSort(e.target.value as "articles" | "name")}
        >
          <option value="articles">Más artículos</option>
          <option value="name">Nombre</option>
        </Select>
      </div>

      {error ? (
        <Alert variant="destructive">No se pudieron cargar los autores.</Alert>
      ) : (
        <div className="overflow-x-auto rounded-xl border bg-card">
          <table className="w-full text-sm">
            <thead>
              <tr>
                <th className={`${HEADER} w-10`}>
                  <span className="sr-only">Artículos</span>
                </th>
                <th className={HEADER}>Autor</th>
                <th className={HEADER}>Artículos</th>
                <th className={HEADER}>Fuentes</th>
                <th className={HEADER}>Último</th>
              </tr>
            </thead>
            {isLoading ? (
              <tbody role="status" aria-label="Cargando autores">
                {Array.from({ length: SKELETON_ROWS }, (_, i) => (
                  <tr key={i} className="border-b">
                    <td colSpan={COLUMNS} className={CELL}>
                      <Skeleton className="h-5 w-full" />
                    </td>
                  </tr>
                ))}
              </tbody>
            ) : items.length === 0 ? (
              <tbody>
                <tr>
                  <td colSpan={COLUMNS} className="px-4 py-10 text-center text-muted-foreground">
                    No hay autores que coincidan.
                  </td>
                </tr>
              </tbody>
            ) : (
              <tbody>
                {items.map((a) => (
                  <ExpandableRow
                    key={a.name}
                    label={a.name}
                    colSpan={COLUMNS}
                    cells={
                      <>
                        <td className={`${CELL} font-medium`}>{a.name}</td>
                        <td className={`${CELL} tabular-nums`}>{a.article_count}</td>
                        <td className={`${CELL} text-muted-foreground`}>
                          {a.sources.map((s) => sourceLabels.get(s) ?? s).join(", ")}
                        </td>
                        <td className={`${CELL} whitespace-nowrap text-muted-foreground`}>
                          {formatDateShort(a.last_published_at)}
                        </td>
                      </>
                    }
                  >
                    <AuthorArticles name={a.name} />
                  </ExpandableRow>
                ))}
              </tbody>
            )}
          </table>
        </div>
      )}

      {total > items.length && (
        <div>
          <Button type="button" variant="outline" size="lg" onClick={() => setLimit((l) => l + PAGE)}>
            Cargar más autores
          </Button>
        </div>
      )}
    </div>
  )
}
