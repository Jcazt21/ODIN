import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react"
import { createPortal } from "react-dom"
import { ChevronDown, X } from "lucide-react"
import { Input } from "@/components/ui/input"
import { filterLocalities, type LocalityEntry } from "@/lib/localities"

/**
 * Un campo del formulario de lugar: se ve como un desplegable, pero se puede
 * escribir dentro y va filtrando.
 *
 * Reemplaza al `<select>` porque con 158 municipios un desplegable nativo
 * obliga a desplazarse a ciegas, y porque el documentalista casi siempre sabe
 * el nombre del lugar antes que su provincia: teclearlo es el camino corto.
 *
 * Al abrirlo sin escribir muestra todas sus opciones, como haría un `<select>`;
 * el texto solo las filtra.
 */
export function LocalityCombobox({
  label,
  entries,
  selected,
  onSelect,
  disabled = false,
  placeholder = "Todas",
  hideLabel = false,
}: {
  label: string
  entries: LocalityEntry[]
  selected: LocalityEntry | undefined
  onSelect: (entry: LocalityEntry | null) => void
  disabled?: boolean
  placeholder?: string
  /** Oculta la etiqueta a la vista sin quitarla del árbol de accesibilidad.
   *  Para filas de filtros donde todos los controles miden lo mismo y el
   *  placeholder ya dice qué es. */
  hideLabel?: boolean
}) {
  const [query, setQuery] = useState("")
  const [open, setOpen] = useState(false)
  const [highlight, setHighlight] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const fieldRef = useRef<HTMLDivElement>(null)
  const [pos, setPos] = useState<{ top: number; left: number; width: number } | null>(null)
  const blurTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  /** Coordenadas de viewport del campo, para colocar el desplegable.
   *
   *  Hace falta porque la lista se renderiza en un portal sobre `document.body`
   *  y ya no puede posicionarse relativa al campo con CSS. El portal, a su vez,
   *  es la única salida: las tarjetas del proyecto usan `backdrop-filter`, que
   *  crea un contexto de apilamiento, y dentro de él ningún z-index alcanza
   *  para pasar por encima de la tarjeta siguiente.
   */
  const measure = useCallback(() => {
    const el = fieldRef.current
    if (!el) return
    const r = el.getBoundingClientRect()
    setPos({ top: r.bottom + 4, left: r.left, width: r.width })
  }, [])

  // useLayoutEffect y no useEffect: mide antes de pintar, para que la lista no
  // aparezca un fotograma en la esquina superior izquierda.
  useLayoutEffect(() => {
    if (open) measure()
  }, [open, measure])

  // Reposicionar mientras está abierto. `capture` para enterarse también del
  // scroll de contenedores internos, no solo del de la ventana.
  useEffect(() => {
    if (!open) return
    const onMove = () => measure()
    window.addEventListener("scroll", onMove, { passive: true, capture: true })
    window.addEventListener("resize", onMove, { passive: true })
    return () => {
      window.removeEventListener("scroll", onMove, { capture: true })
      window.removeEventListener("resize", onMove)
    }
  }, [open, measure])

  const results = useMemo(() => filterLocalities(entries, query), [entries, query])

  // El cierre diferido del blur no debe sobrevivir al desmontaje: si el campo
  // desaparece mientras el temporizador corre, el setState llegaría tarde.
  useEffect(() => () => clearTimeout(blurTimer.current), [])

  /** Mientras está abierto se muestra lo tecleado; cerrado, el nombre elegido.
   *  Así el campo se lee como un desplegable salvo en el momento de escribir. */
  const shown = open ? query : (selected?.name ?? "")

  function openList() {
    if (disabled) return
    setOpen(true)
    setQuery("")
    setHighlight(0)
  }

  function closeList() {
    setOpen(false)
    setQuery("")
  }

  function pick(entry: LocalityEntry | null) {
    onSelect(entry)
    closeList()
    inputRef.current?.blur()
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Escape") {
      closeList()
      return
    }
    if (!open) {
      if (e.key === "ArrowDown" || e.key === "Enter") openList()
      return
    }
    if (e.key === "ArrowDown") {
      e.preventDefault()
      setHighlight((h) => (results.length ? (h + 1) % results.length : 0))
    } else if (e.key === "ArrowUp") {
      e.preventDefault()
      setHighlight((h) => (results.length ? (h - 1 + results.length) % results.length : 0))
    } else if (e.key === "Enter") {
      e.preventDefault()
      if (results[highlight]) pick(results[highlight])
    }
  }

  return (
    <div className="relative flex flex-col gap-1">
      <label className={hideLabel ? "block" : "flex flex-col gap-1"}>
        <span
          className={hideLabel ? "sr-only" : "text-[11.5px]"}
          style={hideLabel ? undefined : { color: "var(--faint)" }}
        >
          {label}
        </span>
        <div className="relative" ref={fieldRef}>
          <Input
            ref={inputRef}
            aria-label={label}
            role="combobox"
            aria-expanded={open}
            aria-autocomplete="list"
            autoComplete="off"
            disabled={disabled}
            placeholder={placeholder}
            className="pr-12"
            value={shown}
            onFocus={openList}
            onClick={openList}
            // El blur se aplaza: si el usuario soltó el clic sobre una opción,
            // ese clic tiene que llegar antes de que la lista se desmonte.
            onBlur={() => {
              blurTimer.current = setTimeout(closeList, 120)
            }}
            onChange={(e) => {
              setQuery(e.target.value)
              setOpen(true)
              setHighlight(0)
            }}
            onKeyDown={onKeyDown}
          />

          {selected && !disabled && (
            <button
              type="button"
              aria-label={`Limpiar ${label}`}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => pick(null)}
              className="absolute top-1/2 right-[26px] -translate-y-1/2 opacity-60 hover:opacity-100"
            >
              <X className="size-3.5" />
            </button>
          )}
          <ChevronDown
            aria-hidden
            className="pointer-events-none absolute top-1/2 right-[9px] size-3.5 -translate-y-1/2"
            style={{ color: "var(--faint)" }}
          />
        </div>
      </label>

      {open &&
        pos &&
        createPortal(
          <ul
          role="listbox"
          aria-label={`Opciones de ${label}`}
          onMouseDown={() => clearTimeout(blurTimer.current)}
          className="fixed z-50 max-h-72 overflow-auto rounded-[7px] border py-1 shadow-lg"
          style={{
            // Token real y OPACO. Antes decía `--surface-1`, que no existe: un
            // var() sin definir no pinta nada y el desplegable quedaba
            // transparente, dejando ver el contenido de atrás.
            background: "var(--surface-3)",
            borderColor: "var(--border)",
            boxShadow: "var(--shadow)",
            top: pos.top,
            left: pos.left,
            width: pos.width,
          }}
        >
          <li>
            <button
              type="button"
              role="option"
              aria-selected={!selected}
              onClick={() => pick(null)}
              className="w-full px-2.5 py-1.5 text-left text-[12.5px]"
              style={{ color: "var(--faint)" }}
            >
              Todas
            </button>
          </li>
          {results.length === 0 && (
            <li className="px-2.5 py-1.5 text-[12px]" style={{ color: "var(--faint)" }}>
              Sin resultados
            </li>
          )}
          {results.map((entry, index) => (
            <li key={entry.id}>
              <button
                type="button"
                role="option"
                aria-selected={selected?.id === entry.id}
                onMouseEnter={() => setHighlight(index)}
                onClick={() => pick(entry)}
                className="flex w-full flex-col items-start gap-0.5 px-2.5 py-1.5 text-left"
                style={{ background: index === highlight ? "var(--surface-3)" : "transparent" }}
              >
                <span className="text-[12.5px]">{entry.name}</span>
                {entry.ancestors.length > 0 && (
                  <span className="text-[10.5px]" style={{ color: "var(--faint)" }}>
                    {entry.ancestors.map((a) => a.name).join(" › ")}
                  </span>
                )}
              </button>
            </li>
          ))}
          </ul>,
          document.body
        )}
    </div>
  )
}
