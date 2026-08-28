import { useId, useState } from "react"
import { useNavigate } from "react-router-dom"
import { useMutation } from "@tanstack/react-query"
import { LocalityPicker } from "@/components/LocalityPicker"
import { Button } from "@/components/ui/button"
import { Select } from "@/components/ui/select"
import { useSources } from "@/lib/queries/sources"
import { useArticleFilterOptions } from "@/lib/queries/articles"
import { createArticle, OdinApiError, type SaveArticlePayload } from "@/lib/odin-api"
import { getUsername } from "@/lib/auth"
import type { PickedLocality } from "@/lib/localities"

/** Alta manual de un reporte (R19).
 *
 *  Existe para que el trabajo no se detenga cuando el análisis automático
 *  falla: el documentalista transcribe la nota y la clasifica a mano. El
 *  análisis (sentimiento, encuadre, actores) NO se pide aquí — se completa
 *  después en el detalle, que ya lo permite, y duplicarlo alargaría el
 *  formulario sin ganar nada.
 *
 *  Los lugares se acumulan en estado local y viajan en el mismo POST, a
 *  diferencia de `LocalitiesCard`, que escribe cada alta al instante porque
 *  allí el artículo ya existe. Acá no hay a qué escribir hasta guardar, y por
 *  eso el guardado es una sola transacción.
 */

type Field =
  | "source"
  | "url"
  | "title"
  | "section"
  | "published_at"
  | "main_topic"
  | "body"

const REQUIRED: Field[] = ["source", "url", "title", "body"]

const EMPTY: Record<Field, string> = {
  source: "",
  url: "",
  title: "",
  section: "",
  published_at: "",
  main_topic: "",
  body: "",
}

export function NewReportPage() {
  const navigate = useNavigate()
  const topicListId = useId()
  const { data: sources } = useSources()
  const { data: facets } = useArticleFilterOptions()

  const [form, setForm] = useState<Record<Field, string>>(EMPTY)
  const [localities, setLocalities] = useState<PickedLocality[]>([])
  const [missing, setMissing] = useState<Field[]>([])
  const [duplicateId, setDuplicateId] = useState<number | null>(null)

  const mutation = useMutation({
    mutationFn: (payload: SaveArticlePayload) => createArticle(payload),
    onSuccess: ({ article, alreadyExisted }) => {
      if (alreadyExisted) {
        // Nada de navegar ni de limpiar: lo escrito es trabajo del
        // documentalista y decidir qué hacer con la nota existente es suyo.
        setDuplicateId(article.id as number)
        return
      }
      navigate(`/reports/${article.id}`)
    },
  })

  function set(field: Field, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }))
    setMissing((prev) => prev.filter((f) => f !== field))
    setDuplicateId(null)
  }

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    const empty = REQUIRED.filter((field) => !form[field].trim())
    setMissing(empty)
    if (empty.length > 0) return

    mutation.mutate({
      source: form.source,
      url: form.url.trim(),
      title: form.title.trim(),
      body: form.body,
      section: form.section.trim() || null,
      published_at: form.published_at || null,
      main_topic: form.main_topic.trim() || null,
      localities: localities.map((l) => ({
        locality_id: l.locality_id,
        kind: l.kind,
        origin: "MANUAL",
        confidence: null,
      })),
    } as unknown as SaveArticlePayload)
  }

  const errorMessage =
    mutation.error instanceof OdinApiError ? mutation.error.message : null

  return (
    <form onSubmit={handleSubmit} className="mx-auto flex max-w-3xl flex-col gap-6 py-6">
      <header className="flex items-baseline justify-between">
        <h1 className="text-[22px] font-semibold">Nuevo reporte</h1>
        <div className="flex gap-2">
          <Button type="button" variant="ghost" onClick={() => navigate("/reports")}>
            Cancelar
          </Button>
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? "Guardando…" : "Guardar reporte"}
          </Button>
        </div>
      </header>

      {duplicateId !== null && (
        <p
          className="rounded-lg border px-4 py-3 text-[13px]"
          style={{ borderColor: "var(--border)", background: "var(--surface-2)" }}
        >
          Esa URL ya está cargada; no se guardó nada nuevo.{" "}
          <button
            type="button"
            className="underline"
            onClick={() => navigate(`/reports/${duplicateId}`)}
          >
            Ver el reporte existente
          </button>
        </p>
      )}

      {errorMessage && (
        <p className="text-[13px]" style={{ color: "var(--danger)" }} role="alert">
          {errorMessage}
        </p>
      )}

      <Section title="Procedencia">
        <Labeled label="Medio" required missing={missing.includes("source")}>
          {(id) => (
            <Select id={id} value={form.source} onChange={(e) => set("source", e.target.value)}>
              <option value="">Elegí un medio…</option>
              {(sources ?? []).map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </Select>
          )}
        </Labeled>
        <Labeled label="URL" required missing={missing.includes("url")}>
          {(id) => (
            <Input id={id} value={form.url} onChange={(v) => set("url", v)} placeholder="https://…" />
          )}
        </Labeled>
        <Labeled label="Título" required missing={missing.includes("title")}>
          {(id) => <Input id={id} value={form.title} onChange={(v) => set("title", v)} />}
        </Labeled>
        <div className="grid grid-cols-2 gap-4">
          <Labeled label="Sección">
            {(id) => <Input id={id} value={form.section} onChange={(v) => set("section", v)} />}
          </Labeled>
          <Labeled label="Publicado">
            {(id) => (
              <Input
                id={id}
                type="date"
                value={form.published_at}
                onChange={(v) => set("published_at", v)}
              />
            )}
          </Labeled>
        </div>
      </Section>

      <Section title="Contenido">
        <Labeled label="Cuerpo" required missing={missing.includes("body")}>
          {(id) => (
            <textarea
              id={id}
              value={form.body}
              onChange={(e) => set("body", e.target.value)}
              rows={10}
              className="w-full rounded-[7px] border px-3 py-2 text-[13px] outline-none"
              style={{ background: "var(--surface-2)", borderColor: "var(--border)" }}
            />
          )}
        </Labeled>
      </Section>

      <Section title="Clasificación">
        <Labeled label="Tema">
          {(id) => (
            <>
              {/* Texto libre con sugerencias: frena que el mismo tema entre
                  como tres variantes, sin construir todavía el catálogo
                  administrable (R4). */}
              <Input
                id={id}
                value={form.main_topic}
                onChange={(v) => set("main_topic", v)}
                list={topicListId}
              />
              <datalist id={topicListId}>
                {(facets?.topics ?? []).map((t) => (
                  <option key={t} value={t} />
                ))}
              </datalist>
            </>
          )}
        </Labeled>
        <div className="flex flex-col gap-2">
          <span className="text-[12px]" style={{ color: "var(--muted-foreground)" }}>
            Lugares
          </span>
          <LocalityPicker
            selected={localities}
            onAdd={(picked) => setLocalities((prev) => [...prev, picked])}
            onRemove={(_picked, index) =>
              setLocalities((prev) => prev.filter((_, i) => i !== index))
            }
          />
        </div>
      </Section>

      <p className="text-[12px]" style={{ color: "var(--faint)" }}>
        Se guardará a nombre de {getUsername() ?? "vos"}.
      </p>
    </form>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-[13px] font-semibold uppercase tracking-wide" style={{ color: "var(--faint)" }}>
        {title}
      </h2>
      {children}
    </section>
  )
}

function Labeled({
  label,
  required = false,
  missing = false,
  children,
}: {
  label: string
  required?: boolean
  missing?: boolean
  children: (id: string) => React.ReactNode
}) {
  const id = useId()
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-[12px]" style={{ color: "var(--muted-foreground)" }}>
        {label}
        {required && " *"}
      </label>
      {children(id)}
      {missing && (
        <span className="text-[11.5px]" style={{ color: "var(--danger)" }}>
          Falta {label.toLowerCase()}.
        </span>
      )}
    </div>
  )
}

function Input({
  id,
  value,
  onChange,
  type = "text",
  placeholder,
  list,
}: {
  id: string
  value: string
  onChange: (value: string) => void
  type?: string
  placeholder?: string
  list?: string
}) {
  return (
    <input
      id={id}
      type={type}
      value={value}
      list={list}
      placeholder={placeholder}
      onChange={(e) => onChange(e.target.value)}
      className="h-9 w-full rounded-[7px] border px-3 text-[13px] outline-none"
      style={{ background: "var(--surface-2)", borderColor: "var(--border)" }}
    />
  )
}
