import { useState, type KeyboardEvent, type MouseEvent } from "react"
import { Check, Pencil, Trash2, X } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { useConfirm } from "@/lib/dialog"
import { OdinApiError } from "@/lib/odin-api"
import { useDeleteTopic, useUpdateTopic } from "@/lib/queries/topics"
import { cn } from "@/lib/utils"
import type { TopicRow } from "@/lib/topic-tree"

const CELL = "px-3.5 py-3 align-middle"
const INDENT_REM = 1.25
const INPUT =
  "h-8 w-full rounded-lg border bg-[var(--surface)] px-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
const ICON_BUTTON =
  "rounded-md p-1.5 text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none disabled:opacity-50"

/** Las acciones viven dentro de una fila expandible: ni el click ni el teclado
 *  deben llegar al contenedor. */
const stop = (e: MouseEvent | KeyboardEvent) => e.stopPropagation()

function errorMessage(error: unknown, fallback: string): string | null {
  if (!error) return null
  return error instanceof OdinApiError ? error.message : fallback
}

/** Celdas de una fila de `/topics`: Tema (con edición inline), Artículos,
 *  Estado (switch) y Acciones. Va dentro de un `<tr>`. */
export function TopicRowCells({ topic }: { topic: TopicRow }) {
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(topic.name)
  const [description, setDescription] = useState(topic.description ?? "")
  const [nameError, setNameError] = useState(false)
  const confirm = useConfirm()
  const updateMutation = useUpdateTopic()
  const deleteMutation = useDeleteTopic()

  const busy = updateMutation.isPending || deleteMutation.isPending
  const dim = !topic.is_active && !editing ? "opacity-45" : undefined
  const error =
    errorMessage(updateMutation.error, "Error guardando el tema.") ??
    errorMessage(deleteMutation.error, "Error borrando el tema.")

  function startEdit() {
    setName(topic.name)
    setDescription(topic.description ?? "")
    setNameError(false)
    updateMutation.reset()
    setEditing(true)
  }

  function cancelEdit() {
    setEditing(false)
    setNameError(false)
    updateMutation.reset()
  }

  async function save() {
    const trimmed = name.trim()
    if (!trimmed) {
      setNameError(true)
      return
    }
    setNameError(false)
    try {
      await updateMutation.mutateAsync({
        id: topic.id,
        payload: { name: trimmed, description: description.trim() },
      })
      setEditing(false)
    } catch {
      // el error queda en updateMutation.error
    }
  }

  function onEditKeyDown(e: KeyboardEvent) {
    if (e.key === "Enter") {
      e.preventDefault()
      void save()
    } else if (e.key === "Escape") {
      e.preventDefault()
      cancelEdit()
    }
  }

  async function handleDelete() {
    const soft = topic.article_count > 0 || topic.child_count > 0
    const ok = await confirm({
      title: `¿Borrar el tema "${topic.name}"?`,
      body: soft ? (
        <>
          Tiene artículos o subtemas, así que <strong>se desactivará</strong> y se conservará su historial.
        </>
      ) : (
        <>
          Está vacío: <strong>se eliminará definitivamente</strong>. Esta acción no se puede deshacer.
        </>
      ),
      confirmLabel: soft ? "Desactivar" : "Eliminar",
      danger: true,
    })
    if (!ok) return
    deleteMutation.mutate(topic.id)
  }

  return (
    <>
      <td className={cn(CELL, dim)} onClick={editing ? stop : undefined} onKeyDown={editing ? stop : undefined}>
        {editing ? (
          <div className="flex flex-col gap-1.5">
            <input
              aria-label="Nombre del tema"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={onEditKeyDown}
              aria-invalid={nameError || undefined}
              autoFocus
              className={INPUT}
            />
            {nameError && (
              <span className="text-xs" style={{ color: "var(--neg)" }}>El nombre es obligatorio</span>
            )}
            <input
              aria-label="Descripción del tema"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              onKeyDown={onEditKeyDown}
              maxLength={500}
              placeholder="Descripción (opcional)"
              className={INPUT}
            />
            {error && (
              <span role="alert" className="text-xs" style={{ color: "var(--neg)" }}>{error}</span>
            )}
          </div>
        ) : (
          <>
            <span
              data-depth={topic.depth}
              style={{ paddingLeft: `${topic.depth * INDENT_REM}rem` }}
              className={topic.depth === 0 ? "font-medium" : undefined}
            >
              {topic.name}
            </span>
            {topic.description && (
              <div
                className="mt-0.5 text-xs text-[var(--faint)]"
                style={{ paddingLeft: `${topic.depth * INDENT_REM}rem` }}
              >
                {topic.description}
              </div>
            )}
          </>
        )}
      </td>
      <td className={cn(CELL, dim)}>
        <Badge variant="secondary" className="tabular-nums">{topic.article_count}</Badge>
      </td>
      <td className={CELL} onClick={stop} onKeyDown={stop}>
        <button
          type="button"
          role="switch"
          aria-checked={topic.is_active}
          aria-label={`${topic.is_active ? "Desactivar" : "Activar"} tema ${topic.name}`}
          disabled={busy}
          onClick={() => updateMutation.mutate({ id: topic.id, payload: { is_active: !topic.is_active } })}
          className="relative inline-flex h-5 w-9 shrink-0 items-center rounded-full border transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none disabled:opacity-50"
          style={{
            background: topic.is_active ? "var(--pos)" : "var(--surface-3)",
            borderColor: topic.is_active ? "var(--pos)" : "var(--border)",
          }}
        >
          <span
            className="inline-block size-3.5 rounded-full bg-white shadow-sm transition-transform"
            style={{ transform: topic.is_active ? "translateX(18px)" : "translateX(2px)" }}
          />
        </button>
      </td>
      <td className={cn(CELL, "text-right")} onClick={stop} onKeyDown={stop}>
        <div className="flex justify-end gap-1">
          {editing ? (
            <>
              <button type="button" disabled={busy} onClick={save} aria-label="Guardar" className={ICON_BUTTON}>
                <Check aria-hidden className="size-3.5" />
              </button>
              <button type="button" onClick={cancelEdit} aria-label="Cancelar edición" className={ICON_BUTTON}>
                <X aria-hidden className="size-3.5" />
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                disabled={busy}
                onClick={startEdit}
                aria-label={`Editar tema ${topic.name}`}
                className={ICON_BUTTON}
              >
                <Pencil aria-hidden className="size-3.5" />
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={handleDelete}
                aria-label={`Borrar tema ${topic.name}`}
                className={cn(ICON_BUTTON, "hover:text-[var(--neg)]")}
              >
                <Trash2 aria-hidden className="size-3.5" />
              </button>
            </>
          )}
        </div>
        {!editing && error && (
          <span role="alert" className="mt-1 block text-xs" style={{ color: "var(--neg)" }}>{error}</span>
        )}
      </td>
    </>
  )
}
