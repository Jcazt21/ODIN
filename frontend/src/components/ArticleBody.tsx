import { ChevronRight } from "lucide-react"

/** Texto de la nota: es de consulta, no lo primero que se lee, así que empieza
 *  cerrado. Al abrirlo se muestra completo (sin scroll interno) con una medida
 *  de línea cómoda. `<details>` da teclado, foco y estado sin JS. */
export function ArticleBody({ body }: { body: string | null }) {
  const paragraphs = (body ?? "")
    .split(/\n+/)
    .map((p) => p.trim())
    .filter(Boolean)
  if (paragraphs.length === 0) return null

  return (
    <details className="group/body border-t pt-6">
      <summary className="inline-flex h-11 cursor-pointer list-none items-center gap-2 rounded-xl px-3 text-[15px] font-semibold outline-none transition-colors duration-150 ease-out marker:hidden hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50 [&::-webkit-details-marker]:hidden">
        <ChevronRight
          aria-hidden
          className="size-5 shrink-0 text-muted-foreground transition-transform duration-150 ease-out group-open/body:rotate-90"
        />
        Leer el artículo completo
      </summary>
      <div className="mt-3 space-y-4 text-base leading-relaxed text-foreground/85">
        {paragraphs.map((p, i) => (
          <p key={i} className="max-w-[75ch] text-pretty">
            {p}
          </p>
        ))}
      </div>
    </details>
  )
}
