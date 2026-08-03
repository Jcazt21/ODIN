import { useState, useEffect, useCallback, type FormEvent } from "react"
import { Pencil, Trash2, Plus, Check, X, Search, ToggleLeft, ToggleRight } from "lucide-react"
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
  listAliases,
  createAlias,
  updateAlias,
  deleteAlias,
  toggleAlias,
  OdinApiError,
  type EntityAlias,
  type AliasPayload,
} from "@/lib/odin-api"

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

const selectClass =
  "h-8 rounded-lg border border-input bg-transparent px-2 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/50 dark:bg-input/30"

const EMPTY_FORM: AliasPayload = { alias: "", canonical_name: "", type: "ORG", is_active: true }

// ─────────────────────────────────────────────────────────────────────────────
// Row (inline edit)
// ─────────────────────────────────────────────────────────────────────────────

function AliasRow({
  alias,
  onUpdated,
  onDeleted,
}: {
  alias: EntityAlias
  onUpdated: (updated: EntityAlias) => void
  onDeleted: (id: number) => void
}) {
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState({ alias: alias.alias, canonical_name: alias.canonical_name, type: alias.type })
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  async function handleSave() {
    setBusy(true)
    setErr(null)
    try {
      const updated = await updateAlias(alias.id, form)
      onUpdated(updated)
      setEditing(false)
    } catch (e) {
      setErr(e instanceof OdinApiError ? e.message : "Error guardando.")
    } finally {
      setBusy(false)
    }
  }

  async function handleDelete() {
    if (!confirm(`¿Eliminar la sigla "${alias.alias}"? Esta acción no se puede deshacer.`)) return
    setBusy(true)
    try {
      await deleteAlias(alias.id)
      onDeleted(alias.id)
    } catch (e) {
      setErr(e instanceof OdinApiError ? e.message : "Error eliminando.")
      setBusy(false)
    }
  }

  async function handleToggle() {
    setBusy(true)
    try {
      const updated = await toggleAlias(alias)
      onUpdated(updated)
    } catch (e) {
      setErr(e instanceof OdinApiError ? e.message : "Error actualizando.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <tr
      className={cn(
        "border-b border-border/50 transition-colors",
        !alias.is_active && "opacity-45",
        editing && "bg-muted/30"
      )}
    >
      {editing ? (
        <>
          <td className="py-2 pl-4 pr-2">
            <Input
              value={form.alias}
              onChange={(e) => setForm((f) => ({ ...f, alias: e.target.value }))}
              className="h-7 text-sm font-mono"
            />
          </td>
          <td className="py-2 px-2">
            <Input
              value={form.canonical_name}
              onChange={(e) => setForm((f) => ({ ...f, canonical_name: e.target.value }))}
              className="h-7 text-sm"
            />
          </td>
          <td className="py-2 px-2">
            <select
              className={cn(selectClass, "h-7 text-xs")}
              value={form.type}
              onChange={(e) => setForm((f) => ({ ...f, type: e.target.value as "ORG" | "PERSON" }))}
            >
              <option value="ORG">ORG</option>
              <option value="PERSON">PERSON</option>
            </select>
          </td>
          <td className="py-2 pr-4 text-right">
            <div className="flex justify-end gap-1">
              {err && <span className="mr-2 text-xs text-destructive">{err}</span>}
              <Button variant="ghost" size="icon-sm" disabled={busy} onClick={handleSave} aria-label="Guardar">
                <Check className="h-3.5 w-3.5" />
              </Button>
              <Button variant="ghost" size="icon-sm" onClick={() => { setEditing(false); setErr(null) }} aria-label="Cancelar">
                <X className="h-3.5 w-3.5" />
              </Button>
            </div>
          </td>
        </>
      ) : (
        <>
          <td className="py-2.5 pl-4 pr-2 font-mono text-sm font-medium">{alias.alias}</td>
          <td className="py-2.5 px-2 text-sm text-muted-foreground">{alias.canonical_name}</td>
          <td className="py-2.5 px-2">
            <Badge variant={alias.type === "ORG" ? "secondary" : "outline"} className="text-xs">
              {alias.type}
            </Badge>
          </td>
          <td className="py-2.5 pr-4 text-right">
            <div className="flex justify-end gap-1">
              {err && <span className="mr-2 text-xs text-destructive">{err}</span>}
              <Button
                variant="ghost"
                size="icon-sm"
                disabled={busy}
                onClick={handleToggle}
                aria-label={alias.is_active ? "Desactivar" : "Activar"}
                title={alias.is_active ? "Desactivar" : "Activar"}
              >
                {alias.is_active
                  ? <ToggleRight className="h-3.5 w-3.5 text-emerald-500" />
                  : <ToggleLeft className="h-3.5 w-3.5 text-muted-foreground" />
                }
              </Button>
              <Button
                variant="ghost"
                size="icon-sm"
                disabled={busy}
                onClick={() => setEditing(true)}
                aria-label="Editar"
              >
                <Pencil className="h-3.5 w-3.5" />
              </Button>
              <Button
                variant="ghost"
                size="icon-sm"
                disabled={busy}
                onClick={handleDelete}
                aria-label="Eliminar"
                className="text-destructive hover:text-destructive"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          </td>
        </>
      )}
    </tr>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// New alias form
// ─────────────────────────────────────────────────────────────────────────────

function NewAliasForm({ onCreated }: { onCreated: (a: EntityAlias) => void }) {
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState<AliasPayload>(EMPTY_FORM)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!form.alias.trim() || !form.canonical_name.trim()) return
    setBusy(true)
    setErr(null)
    try {
      const created = await createAlias({ ...form, alias: form.alias.trim(), canonical_name: form.canonical_name.trim() })
      onCreated(created)
      setForm(EMPTY_FORM)
      setOpen(false)
    } catch (e) {
      setErr(e instanceof OdinApiError ? e.message : "Error creando.")
    } finally {
      setBusy(false)
    }
  }

  if (!open) {
    return (
      <Button
        id="alias-add-btn"
        type="button"
        size="sm"
        variant="outline"
        className="gap-1.5"
        onClick={() => setOpen(true)}
      >
        <Plus className="h-3.5 w-3.5" />
        Nueva sigla
      </Button>
    )
  }

  return (
    <form
      id="alias-new-form"
      onSubmit={handleSubmit}
      className="flex flex-wrap items-end gap-2 rounded-xl border border-border bg-muted/30 p-3"
    >
      <div className="flex-1 min-w-[80px]">
        <label className="mb-1 block text-xs text-muted-foreground">Sigla</label>
        <Input
          id="alias-input-alias"
          value={form.alias}
          onChange={(e) => setForm((f) => ({ ...f, alias: e.target.value.toUpperCase() }))}
          placeholder="MINERD"
          className="h-8 font-mono text-sm"
          required
        />
      </div>
      <div className="flex-[3] min-w-[180px]">
        <label className="mb-1 block text-xs text-muted-foreground">Nombre canónico</label>
        <Input
          id="alias-input-canonical"
          value={form.canonical_name}
          onChange={(e) => setForm((f) => ({ ...f, canonical_name: e.target.value }))}
          placeholder="Ministerio de Educación de la República Dominicana"
          className="h-8 text-sm"
          required
        />
      </div>
      <div>
        <label className="mb-1 block text-xs text-muted-foreground">Tipo</label>
        <select
          id="alias-select-type"
          className={selectClass}
          value={form.type}
          onChange={(e) => setForm((f) => ({ ...f, type: e.target.value as "ORG" | "PERSON" }))}
        >
          <option value="ORG">ORG</option>
          <option value="PERSON">PERSON</option>
        </select>
      </div>
      <div className="flex items-center gap-1.5 pb-0.5">
        {err && <span className="text-xs text-destructive">{err}</span>}
        <Button id="alias-save-btn" type="submit" size="sm" disabled={busy}>
          {busy ? "Guardando…" : "Guardar"}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          onClick={() => { setOpen(false); setErr(null); setForm(EMPTY_FORM) }}
        >
          Cancelar
        </Button>
      </div>
    </form>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Main component
// ─────────────────────────────────────────────────────────────────────────────

export function AliasManager() {
  const [aliases, setAliases] = useState<EntityAlias[]>([])
  const [q, setQ] = useState("")
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async (query?: string) => {
    setLoading(true)
    setError(null)
    try {
      const data = await listAliases(query || undefined)
      setAliases(data)
    } catch (e) {
      setError(e instanceof OdinApiError ? e.message : "No se pudo conectar con la API.")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  // Debounced search
  useEffect(() => {
    const t = setTimeout(() => load(q), 300)
    return () => clearTimeout(t)
  }, [q, load])

  function handleCreated(a: EntityAlias) {
    setAliases((prev) => [...prev, a].sort((x, y) => x.alias.localeCompare(y.alias)))
  }

  function handleUpdated(updated: EntityAlias) {
    setAliases((prev) => prev.map((a) => (a.id === updated.id ? updated : a)))
  }

  function handleDeleted(id: number) {
    setAliases((prev) => prev.filter((a) => a.id !== id))
  }

  const active = aliases.filter((a) => a.is_active).length

  return (
    <div className="w-full space-y-5">
      <Card>
        <CardHeader className="pb-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle className="text-xl">Catálogo de siglas</CardTitle>
              <CardDescription className="mt-0.5">
                {loading
                  ? "Cargando…"
                  : `${aliases.length} siglas · ${active} activas`}
              </CardDescription>
            </div>
            <NewAliasForm onCreated={handleCreated} />
          </div>
          <div className="relative mt-2">
            <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              id="alias-search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Buscar sigla o nombre…"
              className="pl-8"
            />
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
          ) : aliases.length === 0 ? (
            <p className="px-4 pb-4 text-sm text-muted-foreground">
              {q ? "No se encontraron siglas con ese filtro." : "No hay siglas registradas aún."}
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border/70 text-xs font-medium text-muted-foreground">
                    <th className="py-2 pl-4 pr-2 text-left">Sigla</th>
                    <th className="py-2 px-2 text-left">Nombre canónico</th>
                    <th className="py-2 px-2 text-left">Tipo</th>
                    <th className="py-2 pr-4 text-right">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {aliases.map((a) => (
                    <AliasRow
                      key={a.id}
                      alias={a}
                      onUpdated={handleUpdated}
                      onDeleted={handleDeleted}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
