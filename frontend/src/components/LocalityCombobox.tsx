import { useEffect, useMemo, useRef, useState } from "react"
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
}: {
  label: string
  entries: LocalityEntry[]
  selected: LocalityEntry | undefined
  onSelect: (entry: LocalityEntry | null) => void
  disabled?: boolean
  placeholder?: string
}) {
  const [query, setQuery] = useState("")
  const [open, setOpen] = useState(false)
  const [highlight, setHighlight] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const blurTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

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
      <label className="flex flex-col gap-1">
        <span className="text-[11.5px]" style={{ color: "var(--faint)" }}>
          {label}
        </span>
        <div className="relative">
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

      {open && (
        <ul
          role="listbox"
          aria-label={`Opciones de ${label}`}
          onMouseDown={() => clearTimeout(blurTimer.current)}
          className="absolute top-full z-20 mt-1 max-h-60 w-full overflow-auto rounded-[7px] border py-1"
          style={{
            background: "var(--surface-1)",
            borderColor: "var(--border)",
            boxShadow: "var(--shadow)",
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
        </ul>
      )}
    </div>
  )
}
