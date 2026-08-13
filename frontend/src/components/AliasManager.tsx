import { useState, useEffect, useRef, type FormEvent } from "react"
import { Pencil, Trash2, Plus, Check, X, Search } from "lucide-react"
import { Select } from "@/components/ui/select"
import { useConfirm } from "@/lib/dialog"
import {
  useAliases,
  useCreateAlias,
  useUpdateAlias,
  useDeleteAlias,
  useToggleAlias,
} from "@/lib/queries/aliases"
import { OdinApiError, type EntityAlias, type AliasPayload } from "@/lib/odin-api"

const EMPTY_FORM: AliasPayload = { alias: "", canonical_name: "", type: "ORG", is_active: true }

// ─────────────────────────────────────────────────────────────────────────────
// Row (inline edit)
// ─────────────────────────────────────────────────────────────────────────────

function AliasRow({ alias }: { alias: EntityAlias }) {
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState({ alias: alias.alias, canonical_name: alias.canonical_name, type: alias.type })
  const confirm = useConfirm()

  const updateMutation = useUpdateAlias()
  const deleteMutation = useDeleteAlias()
  const toggleMutation = useToggleAlias()

  const busy = updateMutation.isPending || deleteMutation.isPending || toggleMutation.isPending
  const err =
    updateMutation.error instanceof OdinApiError
      ? updateMutation.error.message
      : updateMutation.error
        ? "Error guardando."
        : deleteMutation.error instanceof OdinApiError
          ? deleteMutation.error.message
          : deleteMutation.error
            ? "Error eliminando."
            : toggleMutation.error instanceof OdinApiError
              ? toggleMutation.error.message
              : toggleMutation.error
                ? "Error actualizando."
                : null

  async function handleSave() {
    try {
      await updateMutation.mutateAsync({ id: alias.id, payload: form })
      setEditing(false)
    } catch {
      // el error queda en updateMutation.error
    }
  }

  async function handleDelete() {
    const ok = await confirm({
      title: `¿Eliminar la sigla "${alias.alias}"?`,
      body: "Las menciones que dependan de esta sigla para resolverse dejarán de hacerlo. Esta acción no se puede deshacer.",
      confirmLabel: "Eliminar",
      danger: true,
    })
    if (!ok) return
    deleteMutation.mutate(alias.id)
  }

  async function handleToggle() {
    toggleMutation.mutate(alias)
  }

  return (
    <tr
      className="border-b"
      style={{
        borderColor: "var(--border)",
        opacity: alias.is_active ? 1 : 0.45,
        background: editing ? "var(--surface-2)" : "transparent",
      }}
    >
      {editing ? (
        <>
          <td className="py-2 pr-2 pl-5">
            <input
              value={form.alias}
              onChange={(e) => setForm((f) => ({ ...f, alias: e.target.value }))}
              className="h-7 w-full rounded-[6px] border px-2 font-mono text-sm outline-none"
              style={{ background: "var(--surface)", borderColor: "var(--border)" }}
            />
          </td>
          <td className="px-2 py-2">
            <input
              value={form.canonical_name}
              onChange={(e) => setForm((f) => ({ ...f, canonical_name: e.target.value }))}
              className="h-7 w-full rounded-[6px] border px-2 text-sm outline-none"
              style={{ background: "var(--surface)", borderColor: "var(--border)" }}
            />
          </td>
          <td className="px-2 py-2">
            <Select
              className="h-7 text-xs"
              value={form.type}
              onChange={(e) => setForm((f) => ({ ...f, type: e.target.value as "ORG" | "PERSON" }))}
            >
              <option value="ORG">ORG</option>
              <option value="PERSON">PERSON</option>
            </Select>
          </td>
          <td className="py-2 pr-5 text-right">
            <div className="flex justify-end gap-1">
              {err && (
                <span className="mr-2 text-xs" style={{ color: "var(--neg)" }}>
                  {err}
                </span>
              )}
              <button type="button" disabled={busy} onClick={handleSave} aria-label="Guardar" className="rounded p-1.5" style={{ color: "var(--muted-foreground)" }}>
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
          </td>
        </>
      ) : (
        <>
          <td className="py-2.5 pr-2 pl-5 font-mono text-sm font-medium">{alias.alias}</td>
          <td className="px-2 py-2.5 text-sm" style={{ color: "var(--muted-foreground)" }}>
            {alias.canonical_name}
          </td>
          <td className="px-2 py-2.5">
            <span
              className="rounded-[5px] border px-1.5 py-0.5 text-[10.5px]"
              style={{ background: "var(--surface-2)", borderColor: "var(--border)", color: "var(--muted-foreground)" }}
            >
              {alias.type}
            </span>
          </td>
          <td className="py-2.5 pr-5 text-right">
            <div className="flex justify-end gap-1">
              {err && (
                <span className="mr-2 text-xs" style={{ color: "var(--neg)" }}>
                  {err}
                </span>
              )}
              <button
                type="button"
                role="switch"
                aria-checked={alias.is_active}
                disabled={busy}
                onClick={handleToggle}
                aria-label={alias.is_active ? "Desactivar" : "Activar"}
                title={alias.is_active ? "Desactivar" : "Activar"}
                className="relative mr-1 inline-flex h-5 w-9 shrink-0 items-center rounded-full border transition-colors disabled:opacity-50"
                style={{
                  background: alias.is_active ? "var(--pos)" : "var(--surface-3)",
                  borderColor: alias.is_active ? "var(--pos)" : "var(--border)",
                }}
              >
                <span
                  className="inline-block size-3.5 translate-x-0.5 rounded-full bg-white shadow-sm transition-transform"
                  style={{ transform: alias.is_active ? "translateX(18px)" : "translateX(2px)" }}
                />
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => setEditing(true)}
                aria-label="Editar"
                className="rounded p-1.5"
                style={{ color: "var(--muted-foreground)" }}
              >
                <Pencil className="size-3.5" />
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={handleDelete}
                aria-label="Eliminar"
                className="rounded p-1.5 transition-colors hover:text-[var(--neg)]"
                style={{ color: "var(--muted-foreground)" }}
              >
                <Trash2 className="size-3.5" />
              </button>
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

function NewAliasForm() {
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState<AliasPayload>(EMPTY_FORM)
  const createMutation = useCreateAlias()

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!form.alias.trim() || !form.canonical_name.trim()) return
    try {
      await createMutation.mutateAsync({ ...form, alias: form.alias.trim(), canonical_name: form.canonical_name.trim() })
      setForm(EMPTY_FORM)
      setOpen(false)
    } catch {
      // el error queda en createMutation.error
    }
  }

  const err = createMutation.error instanceof OdinApiError ? createMutation.error.message : createMutation.error ? "Error creando." : null

  if (!open) {
    return (
      <button
        id="alias-add-btn"
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-[13px] font-semibold"
        style={{ background: "var(--primary)", color: "var(--accent-fg)" }}
      >
        <Plus className="size-3.5" />
        Nueva sigla
      </button>
    )
  }

  return (
    <form
      id="alias-new-form"
      onSubmit={handleSubmit}
      className="flex flex-wrap items-end gap-2 rounded-[9px] border p-3"
      style={{ background: "var(--surface-2)", borderColor: "var(--border)" }}
    >
      <div className="min-w-[80px] flex-1">
        <label className="mb-1 block text-xs" style={{ color: "var(--muted-foreground)" }}>
          Sigla
        </label>
        <input
          id="alias-input-alias"
          value={form.alias}
          onChange={(e) => setForm((f) => ({ ...f, alias: e.target.value.toUpperCase() }))}
          placeholder="MINERD"
          required
          className="h-8 w-full rounded-[7px] border px-2 font-mono text-sm outline-none"
          style={{ background: "var(--surface)", borderColor: "var(--border)" }}
        />
      </div>
      <div className="min-w-[180px] flex-[3]">
        <label className="mb-1 block text-xs" style={{ color: "var(--muted-foreground)" }}>
          Nombre canónico
        </label>
        <input
          id="alias-input-canonical"
          value={form.canonical_name}
          onChange={(e) => setForm((f) => ({ ...f, canonical_name: e.target.value }))}
          placeholder="Ministerio de Educación de la República Dominicana"
          required
          className="h-8 w-full rounded-[7px] border px-2 text-sm outline-none"
          style={{ background: "var(--surface)", borderColor: "var(--border)" }}
        />
      </div>
      <div>
        <label className="mb-1 block text-xs" style={{ color: "var(--muted-foreground)" }}>
          Tipo
        </label>
        <Select
          id="alias-select-type"
          value={form.type}
          onChange={(e) => setForm((f) => ({ ...f, type: e.target.value as "ORG" | "PERSON" }))}
        >
          <option value="ORG">ORG</option>
          <option value="PERSON">PERSON</option>
        </Select>
      </div>
      <div className="flex items-center gap-1.5 pb-0.5">
        {err && (
          <span className="text-xs" style={{ color: "var(--neg)" }}>
            {err}
          </span>
        )}
        <button
          id="alias-save-btn"
          type="submit"
          disabled={createMutation.isPending}
          className="rounded-lg px-3 py-1.5 text-[13px] font-semibold disabled:opacity-60"
          style={{ background: "var(--primary)", color: "var(--accent-fg)" }}
        >
          {createMutation.isPending ? "Guardando…" : "Guardar"}
        </button>
        <button
          type="button"
          onClick={() => {
            setOpen(false)
            createMutation.reset()
            setForm(EMPTY_FORM)
          }}
          className="rounded-lg px-3 py-1.5 text-[13px]"
          style={{ color: "var(--muted-foreground)" }}
        >
          Cancelar
        </button>
      </div>
    </form>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Main component
// ─────────────────────────────────────────────────────────────────────────────

export function AliasManager() {
  const [q, setQ] = useState("")
  const [debouncedQ, setDebouncedQ] = useState("")

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

  const { data, isLoading, isFetching, error } = useAliases(debouncedQ || undefined)
  const aliases = data ?? []
  const loading = isLoading || isFetching
  const errorMessage = error instanceof OdinApiError ? error.message : error ? "No se pudo conectar con la API." : null

  const active = aliases.filter((a) => a.is_active).length

  return (
    <div
      className="odin-glass w-full overflow-hidden rounded-xl border"
    >
      <div className="border-b px-5 py-[18px]" style={{ borderColor: "var(--border)" }}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-[19px] font-semibold">Siglas</h1>
            <p className="mt-0.5 text-[12.5px]" style={{ color: "var(--faint)" }}>
              {loading ? "Cargando…" : `${aliases.length} siglas · ${active} activas`}
            </p>
          </div>
          <NewAliasForm />
        </div>
        <div className="relative mt-3">
          <Search className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2" style={{ color: "var(--faint)" }} />
          <input
            id="alias-search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Buscar sigla…"
            className="h-8 w-[180px] rounded-[7px] border pr-2 pl-8 text-[13px] outline-none"
            style={{ background: "var(--surface-2)", borderColor: "var(--border)" }}
          />
        </div>
      </div>

      {errorMessage && (
        <div role="alert" className="m-4 rounded-[7px] border px-3 py-2.5 text-[12.5px]" style={{ background: "var(--neg-soft)", borderColor: "var(--neg)", color: "var(--neg)" }}>
          {errorMessage}
        </div>
      )}

      {loading && aliases.length === 0 ? (
        <div className="space-y-2 p-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-9 w-full rounded" style={{ background: "var(--surface-3)", animation: "odinPulse 1.6s ease-in-out infinite" }} />
          ))}
        </div>
      ) : aliases.length === 0 ? (
        <p className="p-4 text-sm" style={{ color: "var(--muted-foreground)" }}>
          {q ? "No se encontraron siglas con ese filtro." : "No hay siglas registradas aún."}
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: "var(--surface-2)" }}>
                <th
                  className="py-[10px] pr-2 pl-5 text-left font-mono text-[10.5px] font-medium tracking-[0.1em] uppercase"
                  style={{ color: "var(--faint)" }}
                >
                  Sigla
                </th>
                <th className="px-2 py-[10px] text-left font-mono text-[10.5px] font-medium tracking-[0.1em] uppercase" style={{ color: "var(--faint)" }}>
                  Nombre canónico
                </th>
                <th className="px-2 py-[10px] text-left font-mono text-[10.5px] font-medium tracking-[0.1em] uppercase" style={{ color: "var(--faint)" }}>
                  Tipo
                </th>
                <th className="py-[10px] pr-5 text-right font-mono text-[10.5px] font-medium tracking-[0.1em] uppercase" style={{ color: "var(--faint)" }}>
                  Acciones
                </th>
              </tr>
            </thead>
            <tbody>
              {aliases.map((a) => (
                <AliasRow key={a.id} alias={a} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
