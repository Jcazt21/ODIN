import { type SelectHTMLAttributes } from "react"
import { cn } from "@/lib/utils"

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  /** Selects de corrección inline: borde punteado, señal de "editable". */
  dashed?: boolean
}

/**
 * Wrapper propio de `<select>` (README §Design Tokens/§4 "Select propio"):
 * reemplaza los `selectClass` duplicados e inconsistentes de App.tsx,
 * ReportsList.tsx, CanonicalEntityManager.tsx y AliasManager.tsx.
 */
export function Select({ className, dashed, children, ...props }: SelectProps) {
  return (
    <div className="relative">
      <select
        {...props}
        className={cn(
          "h-9 w-full appearance-none rounded-lg border bg-[var(--surface)] px-2.5 pr-7 text-sm",
          "outline-none transition-colors focus-visible:ring-2 focus-visible:ring-[var(--ring)]",
          dashed ? "border-dashed" : "border-solid",
          className
        )}
        style={{ borderColor: dashed ? "var(--border-strong)" : "var(--border)" }}
      >
        {children}
      </select>
      <span
        aria-hidden
        className="pointer-events-none absolute top-1/2 right-[10px] -translate-y-1/2 text-[10px]"
        style={{ color: "var(--faint)" }}
      >
        ▾
      </span>
    </div>
  )
}
