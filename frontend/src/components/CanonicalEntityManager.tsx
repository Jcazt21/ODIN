import { useState, useEffect, useCallback } from "react"
import { Pencil, Check, X, Search, ChevronDown, ChevronRight, GitMerge } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { cn } from "@/lib/utils"
import {
  listCanonicalEntities,
  getCanonicalEntity,
  updateCanonicalEntity,
  mergeCanonicalEntities,
  OdinApiError,
  type CanonicalEntity,
  type CanonicalEntityDetail,
} from "@/lib/odin-api"

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

const selectClass =
  "h-8 rounded-lg border border-input bg-transparent px-2 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/50 dark:bg-input/30"

function formatDate(iso: string | null) {
  if (!iso) return "—"
  return new Date(iso).toLocaleDateString("es-DO", { year: "numeric", month: "short", day: "numeric" })
}

// ─────────────────────────────────────────────────────────────────────────────
// Panel de fusión (dentro de la fila): busca dentro de la lista ya cargada
// ─────────────────────────────────────────────────────────────────────────────

function MergePanel({
  entity,
  candidates,
  onMerged,
  onCancel,
}: {
  entity: CanonicalEntity
  candidates: CanonicalEntity[]
  onMerged: (mergedAwayId: number) => void
  onCancel: () => void
}) {
  const [q, setQ] = useState("")
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const matches = candidates
    .filter((c) => c.id !== entity.id && c.type === entity.type)
    .filter((c) => !q.trim() || c.name.toLowerCase().includes(q.trim().toLowerCase()))
    .slice(0, 8)

  async function handleMerge(target: CanonicalEntity) {
    if (!confirm(`¿Fusionar "${entity.name}" dentro de "${target.name}"? Esta acción no se puede deshacer.`)) return
    setBusy(true)
    setErr(null)
    try {
      await mergeCanonicalEntities(target.id, entity.id)
      onMerged(entity.id)
    } catch (e) {
      setErr(e instanceof OdinApiError ? e.message : "Error fusionando.")
      setBusy(false)
    }
  }

  return (
    <div className="rounded-lg border border-border bg-muted/30 p-3">
      <p className="mb-2 text-xs text-muted-foreground">
        Elige la entidad correcta: <strong>{entity.name}</strong> se fundirá dentro de ella y desaparecerá.
      </p>
      <div className="relative mb-2">
        <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
        <Input
          autoFocus
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Buscar entidad destino…"
          className="h-8 pl-8 text-sm"
        />
      </div>
      {err && <p className="mb-2 text-xs text-destructive">{err}</p>}
      <div className="max-h-40 space-y-1 overflow-y-auto">
        {matches.length === 0 ? (
          <p className="text-xs text-muted-foreground">Sin coincidencias.</p>
        ) : (
          matches.map((c) => (
            <button
              key={c.id}
              type="button"
              disabled={busy}
              onClick={() => handleMerge(c)}
              className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted disabled:opacity-50"
            >
              <span>{c.name}</span>
              <span className="text-xs text-muted-foreground">{c.article_count} artículos</span>
            </button>
          ))
        )}
      </div>
      <div className="mt-2 flex justify-end">
        <Button type="button" size="sm" variant="ghost" disabled={busy} onClick={onCancel}>
          Cancelar
        </Button>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Fila
// ─────────────────────────────────────────────────────────────────────────────

function CanonicalEntityRow({
  entity,
  allEntities,
  onUpdated,
  onMerged,
}: {
  entity: CanonicalEntity
  allEntities: CanonicalEntity[]
  onUpdated: (updated: CanonicalEntity) => void
  onMerged: (mergedAwayId: number) => void
}) {
  const [editing, setEditing] = useState(false)
  const [merging, setMerging] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [form, setForm] = useState({ name: entity.name, description: entity.description ?? "" })
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [detail, setDetail] = useState<CanonicalEntityDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  async function handleSave() {
    setBusy(true)
    setErr(null)
    try {
      const updated = await updateCanonicalEntity(entity.id, {
        name: form.name.trim(),
        description: form.description.trim(),
      })
      onUpdated({ ...updated, article_count: entity.article_count, total_mentions: entity.total_mentions })
      setEditing(false)
    } catch (e) {
      setErr(e instanceof OdinApiError ? e.message : "Error guardando.")
    } finally {
      setBusy(false)
    }
  }

  async function handleExpand() {
    const next = !expanded
    setExpanded(next)
    if (next && !detail) {
      setDetailLoading(true)
      try {
        setDetail(await getCanonicalEntity(entity.id))
      } catch {
        // silencioso: el detalle es progresivo, no crítico para la fila
      } finally {
        setDetailLoading(false)
      }
    }
  }

  return (
    <div className={cn("border-b border-border/50 transition-colors", editing && "bg-muted/30")}>
      <div className="flex items-center gap-2 py-2.5 pl-2 pr-4">
        <button
          type="button"
          onClick={handleExpand}
          className="shrink-0 rounded p-1 text-muted-foreground hover:bg-muted"
          aria-label={expanded ? "Contraer" : "Expandir"}
        >
          {expanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
        </button>

        {editing ? (
          <>
            <div className="flex flex-1 flex-wrap gap-2">
              <Input
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                className="h-7 flex-1 min-w-[140px] text-sm font-medium"
              />
              <Input
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                placeholder="Descripción (opcional)"
                className="h-7 flex-[2] min-w-[160px] text-sm text-muted-foreground"
              />
            </div>
            <div className="flex items-center gap-1">
              {err && <span className="mr-1 text-xs text-destructive">{err}</span>}
              <Button variant="ghost" size="icon-sm" disabled={busy} onClick={handleSave} aria-label="Guardar">
                <Check className="h-3.5 w-3.5" />
              </Button>
              <Button variant="ghost" size="icon-sm" onClick={() => { setEditing(false); setErr(null) }} aria-label="Cancelar">
                <X className="h-3.5 w-3.5" />
              </Button>
            </div>
          </>
        ) : (
          <>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="truncate text-sm font-medium">{entity.name}</span>
                <Badge variant={entity.type === "ORG" ? "secondary" : "outline"} className="shrink-0 text-xs">
                  {entity.type}
                </Badge>
              </div>
              {entity.description && (
                <p className="truncate text-xs text-muted-foreground">{entity.description}</p>
              )}
            </div>
            <div className="hidden shrink-0 text-right text-xs text-muted-foreground sm:block">
              <div>{entity.article_count} artículos</div>
              <div>{entity.total_mentions} menciones</div>
            </div>
            <div className="flex shrink-0 items-center gap-1">
              {err && <span className="mr-1 text-xs text-destructive">{err}</span>}
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={() => setMerging((v) => !v)}
                aria-label="Fusionar"
                title="Fusionar con otra entidad"
              >
                <GitMerge className="h-3.5 w-3.5" />
              </Button>
              <Button variant="ghost" size="icon-sm" onClick={() => setEditing(true)} aria-label="Editar">
                <Pencil className="h-3.5 w-3.5" />
              </Button>
            </div>
          </>
        )}
      </div>

      {merging && (
        <div className="px-4 pb-3">
          <MergePanel
            entity={entity}
            candidates={allEntities}
            onCancel={() => setMerging(false)}
            onMerged={(id) => { setMerging(false); onMerged(id) }}
          />
        </div>
      )}

      {expanded && (
        <div className="px-4 pb-3 pl-9">
          {detailLoading ? (
            <Skeleton className="h-16 w-full" />
          ) : !detail || detail.articles.length === 0 ? (
            <p className="text-xs text-muted-foreground">Sin artículos vinculados.</p>
          ) : (
            <ul className="space-y-1 text-xs">
              {detail.articles.map((a) => (
                <li key={a.article_id} className="flex items-center justify-between gap-2 rounded-md px-2 py-1 hover:bg-muted/50">
                  <a href={a.url} target="_blank" rel="noreferrer" className="truncate text-foreground hover:underline">
                    {a.title}
                  </a>
                  <span className="shrink-0 text-muted-foreground">
                    {formatDate(a.published_at)} · {a.mentions_count} menc.
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Componente principal
// ─────────────────────────────────────────────────────────────────────────────

export function CanonicalEntityManager() {
  const [items, setItems] = useState<CanonicalEntity[]>([])
  const [q, setQ] = useState("")
  const [typeFilter, setTypeFilter] = useState<"" | "ORG" | "PERSON">("")
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async (query?: string, type?: "" | "ORG" | "PERSON") => {
    setLoading(true)
    setError(null)
    try {
      const data = await listCanonicalEntities({
        q: query || undefined,
        type: (type || undefined) as "ORG" | "PERSON" | undefined,
        limit: 200,
      })
      setItems(data.items)
      setTotal(data.total)
    } catch (e) {
      setError(e instanceof OdinApiError ? e.message : "No se pudo conectar con la API.")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    const t = setTimeout(() => load(q, typeFilter), 300)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, typeFilter])

  function handleUpdated(updated: CanonicalEntity) {
    setItems((prev) => prev.map((it) => (it.id === updated.id ? updated : it)))
  }

  function handleMerged(mergedAwayId: number) {
    // Los conteos del destino cambiaron (ganó las menciones de la fusionada):
    // más simple y correcto recargar que intentar sumarlos a mano en cliente.
    setItems((prev) => prev.filter((it) => it.id !== mergedAwayId))
    load(q, typeFilter)
  }

  return (
    <div className="w-full space-y-5">
      <Card>
        <CardHeader className="pb-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle className="text-xl">Entidades canónicas</CardTitle>
              <CardDescription className="mt-0.5">
                {loading ? "Cargando…" : `${total} figuras/organizaciones únicas`}
              </CardDescription>
            </div>
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Buscar entidad…"
                className="pl-8"
              />
            </div>
            <select
              className={selectClass}
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value as "" | "ORG" | "PERSON")}
            >
              <option value="">Todos los tipos</option>
              <option value="PERSON">PERSON</option>
              <option value="ORG">ORG</option>
            </select>
          </div>
        </CardHeader>

        <CardContent className="p-0 pb-1">
          {error && (
            <Alert variant="destructive" className="mx-4 mb-4 w-auto">
              <AlertTitle>Error</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {loading ? (
            <div className="space-y-2 px-4 pb-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-9 w-full" />
              ))}
            </div>
          ) : items.length === 0 ? (
            <p className="px-4 pb-4 text-sm text-muted-foreground">
              {q ? "No se encontraron entidades con ese filtro." : "Aún no hay entidades canónicas guardadas."}
            </p>
          ) : (
            <div>
              {items.map((entity) => (
                <CanonicalEntityRow
                  key={entity.id}
                  entity={entity}
                  allEntities={items}
                  onUpdated={handleUpdated}
                  onMerged={handleMerged}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
