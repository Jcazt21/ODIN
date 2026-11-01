import type { ReactNode } from "react"

interface PageHeaderProps {
  title: string
  subtitle?: ReactNode
  /** Texto ya formateado de la píldora, p. ej. «12 autores». */
  count?: string
}

/** Cabecera común de las páginas: título, píldora de conteo y subtítulo. */
export function PageHeader({ title, subtitle, count }: PageHeaderProps) {
  return (
    <header className="space-y-1">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {count && (
          <p className="inline-flex h-7 items-center rounded-full bg-[var(--accent-soft)] px-3 text-sm text-primary">
            {count}
          </p>
        )}
      </div>
      {subtitle && <p className="max-w-[60ch] text-sm text-muted-foreground">{subtitle}</p>}
    </header>
  )
}
