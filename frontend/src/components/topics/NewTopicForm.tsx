import { useState, type FormEvent } from "react"
import { Plus } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Select } from "@/components/ui/select"
import { OdinApiError } from "@/lib/odin-api"
import { useCreateTopic } from "@/lib/queries/topics"
import type { TopicRow } from "@/lib/topic-tree"

const INPUT =
  "h-9 w-full rounded-lg border bg-[var(--surface)] px-2.5 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
const LABEL = "mb-1 block text-xs text-muted-foreground"

interface NewTopicFormProps {
  /** Filas planas del árbol: de ahí salen las opciones de tema padre. */
  topics: TopicRow[]
  /** Control externo (p. ej. el CTA del estado vacío). Sin él, el estado es propio. */
  open?: boolean
  onOpenChange?: (open: boolean) => void
}

/** Alta inline de un tema: nombre, descripción y padre opcional. El slug lo
 *  deriva el backend a partir del nombre. */
export function NewTopicForm({ topics, open: openProp, onOpenChange }: NewTopicFormProps) {
  const [openState, setOpenState] = useState(false)
  const open = openProp ?? openState
  const setOpen = (value: boolean) => {
    setOpenState(value)
    onOpenChange?.(value)
  }
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [parentId, setParentId] = useState("")
  const [nameError, setNameError] = useState(false)
  const createMutation = useCreateTopic()

  function reset() {
    setName("")
    setDescription("")
    setParentId("")
    setNameError(false)
    createMutation.reset()
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) {
      setNameError(true)
      return
    }
    setNameError(false)
    try {
      await createMutation.mutateAsync({
        name: trimmed,
        description: description.trim(),
        parent_id: parentId ? Number(parentId) : null,
      })
      reset()
      setOpen(false)
    } catch {
      // el error queda en createMutation.error
    }
  }

  const serverError =
    createMutation.error instanceof OdinApiError
      ? createMutation.error.message
      : createMutation.error
        ? "Error creando el tema."
        : null

  if (!open) {
    return (
      <div>
        <Button type="button" onClick={() => setOpen(true)}>
          <Plus aria-hidden className="size-3.5" />
          Nuevo tema
        </Button>
      </div>
    )
  }

  return (
    <form
      onSubmit={handleSubmit}
      noValidate
      className="flex flex-wrap items-start gap-3 rounded-xl border bg-card p-3"
      style={{ boxShadow: "var(--shadow-sm)" }}
    >
      <div className="min-w-[180px] flex-1">
        <label htmlFor="new-topic-name" className={LABEL}>Nombre</label>
        <input
          id="new-topic-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          aria-invalid={nameError || undefined}
          className={INPUT}
        />
        {nameError && (
          <p className="mt-1 text-xs" style={{ color: "var(--neg)" }}>El nombre es obligatorio</p>
        )}
      </div>
      <div className="min-w-[220px] flex-[2]">
        <label htmlFor="new-topic-description" className={LABEL}>Descripción</label>
        <input
          id="new-topic-description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          maxLength={500}
          className={INPUT}
        />
      </div>
      <div className="min-w-[180px] flex-1">
        <label htmlFor="new-topic-parent" className={LABEL}>Tema padre</label>
        <Select id="new-topic-parent" value={parentId} onChange={(e) => setParentId(e.target.value)}>
          <option value="">Sin padre (raíz)</option>
          {topics
            .filter((t) => t.is_active)
            .map((t) => (
              <option key={t.id} value={t.id}>
                {"  ".repeat(t.depth)}
                {t.name}
              </option>
            ))}
        </Select>
      </div>
      <div className="flex items-center gap-2 self-end pb-0.5">
        {serverError && (
          <span role="alert" className="text-xs" style={{ color: "var(--neg)" }}>{serverError}</span>
        )}
        <Button type="submit" disabled={createMutation.isPending}>
          {createMutation.isPending ? "Creando…" : "Crear tema"}
        </Button>
        <Button
          type="button"
          variant="ghost"
          onClick={() => {
            reset()
            setOpen(false)
          }}
        >
          Cancelar
        </Button>
      </div>
    </form>
  )
}
