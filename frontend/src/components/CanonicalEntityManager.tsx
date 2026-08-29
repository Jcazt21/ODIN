import { useState, useEffect, useRef } from "react"
import { Link } from "react-router-dom"
import { Pencil, Check, X, Search, ChevronDown, ChevronRight, GitMerge } from "lucide-react"
import { Select } from "@/components/ui/select"
import { useConfirm } from "@/lib/dialog"
import { ENTITY_TYPE_LABELS } from "@/lib/labels"
import { computeSentimentAggregate } from "@/lib/sentiment-aggregate"
import { SentimentCompositionBar } from "@/components/SentimentCompositionBar"
import { SourceSentimentBreakdown } from "@/components/SourceSentimentBreakdown"
import { groupArticlesBySource } from "@/lib/sentiment-by-source"
import {
  useCanonicalEntities,
  useCanonicalEntity,
  useUpdateCanonicalEntity,
  useMergeCanonicalEntities,
} from "@/lib/queries/canonical-entities"
import { OdinApiError, type CanonicalEntity } from "@/lib/odin-api"

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
  onMerged: () => void
  onCancel: () => void
}) {
  const [q, setQ] = useState("")
  const confirm = useConfirm()
  const mergeMutation = useMergeCanonicalEntities()

  const matches = candidates
    .filter((c) => c.id !== entity.id && c.type === entity.type)
    .filter((c) => !q.trim() || c.name.toLowerCase().includes(q.trim().toLowerCase()))
    .slice(0, 8)

  async function handleMerge(target: CanonicalEntity) {
    const ok = await confirm({
      title: `¿Fusionar "${entity.name}" con "${target.name}"?`,
      body: "Las menciones de la entidad de origen se transferirán al destino. Esta acción no se puede deshacer.",
      confirmLabel: "Fusionar",
      danger: true,
    })
    if (!ok) return
    try {
      await mergeMutation.mutateAsync({ targetId: target.id, sourceId: entity.id })
      onMerged()
    } catch {
      // el error queda en mergeMutation.error, mostrado abajo
    }
  }

  const err = mergeMutation.error instanceof OdinApiError ? mergeMutation.error.message : mergeMutation.error ? "Error fusionando." : null

  return (
    <div className="rounded-[9px] border p-3" style={{ background: "var(--surface-2)", borderColor: "var(--border)" }}>
      <p className="mb-2 text-xs" style={{ color: "var(--muted-foreground)" }}>
        Elige la entidad correcta: <strong>{entity.name}</strong> se fundirá dentro de ella y desaparecerá.
      </p>
      <div className="relative mb-2">
        <Search className="absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2" style={{ color: "var(--faint)" }} />
        <input
          autoFocus
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Buscar entidad destino…"
          className="h-8 w-full rounded-[7px] border pr-2 pl-8 text-sm outline-none"
          style={{ background: "var(--surface)", borderColor: "var(--border)" }}
        />
      </div>
      {err && (
        <p className="mb-2 text-xs" style={{ color: "var(--neg)" }}>
          {err}
        </p>
      )}
      <div className="max-h-40 space-y-1 overflow-y-auto">
        {matches.length === 0 ? (
          <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>
            Sin coincidencias.
          </p>
        ) : (
          matches.map((c) => (
            <button
              key={c.id}
              type="button"
              disabled={mergeMutation.isPending}
              onClick={() => handleMerge(c)}
              className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-sm disabled:opacity-50"
              style={{ background: "transparent" }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surface-3)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
            >
              <span>{c.name}</span>
              <span className="text-xs" style={{ color: "var(--muted-foreground)" }}>
                {c.article_count} artículos
              </span>
            </button>
          ))
        )}
      </div>
      <div className="mt-2 flex justify-end">
        <button
          type="button"
          disabled={mergeMutation.isPending}
          onClick={onCancel}
          className="rounded-[6px] px-2.5 py-1 text-xs"
          style={{ color: "var(--muted-foreground)" }}
        >
          Cancelar
        </button>
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
}: {
  entity: CanonicalEntity
  allEntities: CanonicalEntity[]
}) {
  const [editing, setEditing] = useState(false)
  const [merging, setMerging] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [form, setForm] = useState({ name: entity.name, description: entity.description ?? "" })

  const updateMutation = useUpdateCanonicalEntity()
  const { data: detail, isLoading: detailLoading } = useCanonicalEntity(entity.id, expanded)

  async function handleSave() {
    try {
      await updateMutation.mutateAsync({
        id: entity.id,
        payload: { name: form.name.trim(), description: form.description.trim() },
      })
      setEditing(false)
    } catch {
      // el error queda en updateMutation.error, mostrado abajo
    }
  }

  const err = updateMutation.error instanceof OdinApiError ? updateMutation.error.message : updateMutation.error ? "Error guardando." : null

  return (
    <div className="border-b" style={{ borderColor: "var(--border)" }}>
      <div className="flex items-center gap-3 px-5 py-3.5">
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="shrink-0 rounded p-1"
          style={{ color: "var(--muted-foreground)" }}
          aria-label={expanded ? "Contraer" : "Expandir"}
        >
          {expanded ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
        </button>

        {editing ? (
          <>
            <div className="flex flex-1 flex-wrap gap-2">
              <input
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                className="h-7 min-w-[140px] flex-1 rounded-[7px] border px-2 text-sm font-medium outline-none"
                style={{ background: "var(--surface-2)", borderColor: "var(--border)" }}
              />
              <input
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                placeholder="Descripción (opcional)"
                className="h-7 min-w-[160px] flex-[2] rounded-[7px] border px-2 text-sm outline-none"
                style={{ background: "var(--surface-2)", borderColor: "var(--border)", color: "var(--muted-foreground)" }}
              />
            </div>
            <div className="flex items-center gap-1">
              {err && (
                <span className="mr-1 text-xs" style={{ color: "var(--neg)" }}>
                  {err}
                </span>
              )}
              <button type="button" disabled={updateMutation.isPending} onClick={handleSave} aria-label="Guardar" className="rounded p-1.5" style={{ color: "var(--muted-foreground)" }}>
                <Check className="size-3.5" />
              </button>
              <button
                type="button"
                onClick={() => {
                  setEditing(false)
                  updateMutation.reset()
                }}
                aria-label="Cancelar"
                className="rounded p-1.5"
                style={{ color: "var(--muted-foreground)" }}
              >
                <X className="size-3.5" />
              </button>
            </div>
          </>
        ) : (
          <>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="truncate text-[14px] font-semibold">{entity.name}</span>
                <span
                  className="shrink-0 rounded-[5px] border px-1.5 py-0.5 text-[10.5px]"
                  style={{ background: "var(--surface-2)", borderColor: "var(--border)", color: "var(--muted-foreground)" }}
                >
                  {ENTITY_TYPE_LABELS[entity.type] ?? entity.type}
                </span>
              </div>
              {entity.description && (
                <p className="truncate text-xs" style={{ color: "var(--muted-foreground)" }}>
                  {entity.description}
                </p>
              )}
            </div>
            <div className="hidden shrink-0 text-right font-mono text-[11.5px] sm:block" style={{ color: "var(--faint)" }}>
              {entity.article_count} art. · {entity.total_mentions} menc.
            </div>
            <div className="flex shrink-0 items-center gap-1.5">
              {err && (
                <span className="mr-1 text-xs" style={{ color: "var(--neg)" }}>
                  {err}
                </span>
              )}
              <button
                type="button"
                onClick={() => setMerging((v) => !v)}
                aria-label="Fusionar"
                title="Fusionar con otra entidad"
                className="inline-flex items-center gap-1 rounded-[6px] border px-2 py-1 text-[11.5px]"
                style={{ background: "var(--surface-2)", borderColor: "var(--border)" }}
              >
                <GitMerge className="size-3.5" />
                Fusionar
              </button>
              <button
                type="button"
                onClick={() => setEditing(true)}
                aria-label="Editar"
                className="inline-flex items-center gap-1 rounded-[6px] border px-2 py-1 text-[11.5px]"
                style={{ background: "var(--surface-2)", borderColor: "var(--border)" }}
              >
                <Pencil className="size-3.5" />
                Editar
              </button>
            </div>
          </>
        )}
      </div>

      {merging && (
        <div className="px-5 pb-3">
          <MergePanel
            entity={entity}
            candidates={allEntities}
            onCancel={() => setMerging(false)}
            onMerged={() => setMerging(false)}
          />
        </div>
      )}

      {expanded && (
        <div className="px-5 pb-3 pl-11">
          {detailLoading ? (
            <div className="h-16 w-full rounded" style={{ background: "var(--surface-3)", animation: "odinPulse 1.6s ease-in-out infinite" }} />
          ) : !detail || detail.articles.length === 0 ? (
            <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>
              Sin artículos vinculados.
            </p>
          ) : (
            <>
              {(() => {
                const aggregate = computeSentimentAggregate(detail.articles)
                return aggregate ? (
                  <div className="mb-3 flex flex-col gap-3">
                    <SentimentCompositionBar aggregate={aggregate} />
                    {/* El mismo dato partido por periódico: quién habla bien y
                        quién habla mal de este actor (R3). */}
                    <SourceSentimentBreakdown articles={detail.articles} />
                  </div>
                ) : null
              })()}
              {/* Agrupados por medio y en el MISMO orden que "Trato por medio",
                  para poder bajar del porcentaje de un medio directo a sus notas. */}
              <div className="flex flex-col gap-3">
                {groupArticlesBySource(detail.articles).map(({ source, sourceName, articles }) => (
                  <div key={source} className="flex flex-col gap-1">
                    <div className="flex items-baseline gap-2 px-2">
                      <h5 className="text-[11.5px] font-semibold">{sourceName}</h5>
                      <span className="font-mono text-[10.5px]" style={{ color: "var(--faint)" }}>
                        {articles.length} {articles.length === 1 ? "artículo" : "artículos"}
                      </span>
                    </div>
                    <ul className="space-y-1 text-xs">
                      {articles.map((a) => (
                        <li
                          key={a.article_id}
                          className="flex items-center justify-between gap-2 rounded-md px-2 py-1"
                        >
                          <Link to={`/reports/${a.article_id}`} className="truncate hover:underline">
                            {a.title}
                          </Link>
                          <span className="shrink-0" style={{ color: "var(--muted-foreground)" }}>
                            {formatDate(a.published_at)} · {a.mentions_count} menc.
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </>
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
  const [q, setQ] = useState("")
  const [debouncedQ, setDebouncedQ] = useState("")
  const [typeFilter, setTypeFilter] = useState<"" | "ORG" | "PERSON">("")

  const isFirstLoad = useRef(true)
  useEffect(() => {
    if (isFirstLoad.current) {
      isFirstLoad.current = false
      setDebouncedQ(q)
      return
    }
    const t = setTimeout(() => setDebouncedQ(q), 300)
    return () => clearTimeout(t)
  }, [q])

  const { data, isLoading, isFetching, error } = useCanonicalEntities({
    q: debouncedQ || undefined,
    type: typeFilter || undefined,
    limit: 200,
  })

  const items = data?.items ?? []
  const total = data?.total ?? 0
  const loading = isLoading || isFetching
  const errorMessage = error instanceof OdinApiError ? error.message : error ? "No se pudo conectar con la API." : null

  return (
    <div
      className="odin-glass w-full overflow-hidden rounded-xl border"
    >
      <div className="border-b px-5 py-[18px]" style={{ borderColor: "var(--border)" }}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-[19px] font-semibold">Entidades canónicas</h1>
            <p className="mt-0.5 text-[12.5px]" style={{ color: "var(--faint)" }}>
              {loading ? "Cargando…" : `${total} figuras/organizaciones únicas`}
            </p>
          </div>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <div className="relative min-w-[200px] flex-1">
            <Search className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2" style={{ color: "var(--faint)" }} />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Buscar entidad…"
              className="h-8 w-full rounded-[7px] border pr-2 pl-8 text-[13px] outline-none"
              style={{ background: "var(--surface-2)", borderColor: "var(--border)" }}
            />
          </div>
          <Select
            className="w-auto"
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value as "" | "ORG" | "PERSON")}
          >
            <option value="">Todos los tipos</option>
            <option value="PERSON">Persona</option>
            <option value="ORG">Organización</option>
          </Select>
        </div>
      </div>

      {errorMessage && (
        <div role="alert" className="m-4 rounded-[7px] border px-3 py-2.5 text-[12.5px]" style={{ background: "var(--neg-soft)", borderColor: "var(--neg)", color: "var(--neg)" }}>
          {errorMessage}
        </div>
      )}

      {loading && items.length === 0 ? (
        <div className="space-y-2 p-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-9 w-full rounded" style={{ background: "var(--surface-3)", animation: "odinPulse 1.6s ease-in-out infinite" }} />
          ))}
        </div>
      ) : items.length === 0 ? (
        <p className="p-4 text-sm" style={{ color: "var(--muted-foreground)" }}>
          {q ? "No se encontraron entidades con ese filtro." : "Aún no hay entidades canónicas guardadas."}
        </p>
      ) : (
        <div>
          {items.map((entity) => (
            <CanonicalEntityRow key={entity.id} entity={entity} allEntities={items} />
          ))}
        </div>
      )}
    </div>
  )
}
