import { useState, type ReactNode } from "react"
import { ChevronRight } from "lucide-react"
import { cn } from "@/lib/utils"

interface ExpandableRowProps {
  /** Nombre del elemento, para el nombre accesible del botón. */
  label: string
  /** Columnas totales de la tabla (incluida la del chevron). */
  colSpan: number
  /** Celdas `<td>` de la fila, a continuación del chevron. */
  cells: ReactNode
  /** Contenido desplegado: no se monta (ni pide datos) hasta expandir. */
  children: ReactNode
}

/** Fila de tabla con un chevron que despliega una fila de detalle debajo. Va
 *  dentro de un `<tbody>`. */
export function ExpandableRow({ label, colSpan, cells, children }: ExpandableRowProps) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <tr className="border-b transition-colors duration-150 hover:bg-muted/50">
        <td className="w-10 px-2 py-2 align-middle">
          <button
            type="button"
            aria-expanded={open}
            aria-label={`${open ? "Ocultar" : "Ver"} artículos de ${label}`}
            onClick={() => setOpen((v) => !v)}
            className="inline-flex size-8 items-center justify-center rounded-md text-muted-foreground transition-colors duration-150 hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
          >
            <ChevronRight
              aria-hidden
              className={cn("size-4 transition-transform duration-150", open && "rotate-90")}
            />
          </button>
        </td>
        {cells}
      </tr>
      {open && (
        <tr className="border-b bg-muted/30">
          <td colSpan={colSpan} className="p-0">
            <div className="odin-expand">
              <div className="min-h-0 overflow-hidden px-4 py-3">{children}</div>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}
