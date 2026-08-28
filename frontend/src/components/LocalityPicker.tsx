import { useMemo, useState } from "react"
import { MapPin, Plus, X } from "lucide-react"
import { LocalityCombobox } from "@/components/LocalityCombobox"
import { Button } from "@/components/ui/button"
import { Select } from "@/components/ui/select"
import { useLocalityTree } from "@/lib/queries/localities"
import {
  ALL,
  EMPTY_CHOICE,
  VISIBLE_LEVELS,
  choiceFromEntry,
  clearFrom,
  entriesAtLevel,
  indexTree,
  type LocalityEntry,
  type PickedLocality,
  type VisibleLevel,
} from "@/lib/localities"

const FIELD_LABELS: Record<VisibleLevel, string> = {
  PAIS: "País",
  MACRORREGION: "Región",
  PROVINCIA: "Provincia",
  MUNICIPIO: "Municipio",
}

export function LocalityPicker({
  selected,
  onAdd,
  onRemove,
  disabled = false,
}: {
  selected: PickedLocality[]
  onAdd: (picked: { locality_id: number; kind: string; label: string }) => void
  onRemove: (picked: PickedLocality, index: number) => void
  disabled?: boolean
}) {
  const { data: tree, isLoading, error } = useLocalityTree()
  const [choice, setChoice] = useState<Record<VisibleLevel, string>>(EMPTY_CHOICE)
  const [kind, setKind] = useState("HECHO")

  const { entries } = useMemo(() => indexTree(tree ?? []), [tree])

  const byId = useMemo(() => {
    const map = new Map<number, LocalityEntry>()
    for (const entry of entries) map.set(entry.id, entry)
    return map
  }, [entries])

  const chosen = useMemo(() => {
    const out = {} as Record<VisibleLevel, LocalityEntry | undefined>
    for (const level of VISIBLE_LEVELS) {
      const value = choice[level]
      out[level] = value === ALL ? undefined : byId.get(Number(value))
    }
    return out
  }, [choice, byId])

  /** Opciones de cada campo: el nivel completo, acotado al ancestro elegido
   *  más cercano si lo hay.
   *
   *  Sin nada elegido arriba, cada campo ofrece TODO su nivel — que es lo que
   *  permite ir directo a Municipio y buscar entre los 158 sin pasar por
   *  País, Región y Provincia. */
  const options = useMemo(() => {
    const out = {} as Record<VisibleLevel, LocalityEntry[]>
    out.PAIS = entriesAtLevel(entries, "PAIS")
    out.MACRORREGION = entriesAtLevel(entries, "MACRORREGION", chosen.PAIS?.id)
    out.PROVINCIA = entriesAtLevel(
      entries,
      "PROVINCIA",
      chosen.MACRORREGION?.id ?? chosen.PAIS?.id
    )
    out.MUNICIPIO = entriesAtLevel(
      entries,
      "MUNICIPIO",
      chosen.PROVINCIA?.id ?? chosen.MACRORREGION?.id ?? chosen.PAIS?.id
    )
    return out
  }, [entries, chosen])

  /** El nodo efectivamente elegido: el más específico que no quedó en "Todas".
   *  Ese nodo ES el alcance de la noticia. */
  const picked = useMemo(() => {
    for (let i = VISIBLE_LEVELS.length - 1; i >= 0; i--) {
      const entry = chosen[VISIBLE_LEVELS[i]]
      if (entry) return entry
    }
    return undefined
  }, [chosen])

  /** Elegir en cualquier campo rellena los de ARRIBA con sus ancestros y
   *  limpia los de ABAJO. Por eso escoger "Tamboril" deja puestos Provincia,
   *  Región y País de una vez, sin tocarlos. */
  function handleSelect(level: VisibleLevel, entry: LocalityEntry | null) {
    setChoice((current) => (entry ? choiceFromEntry(entry) : clearFrom(current, level)))
  }

  function handleAdd() {
    if (!picked) return
    onAdd({ locality_id: picked.id, kind, label: picked.breadcrumb })
    // El país se conserva: la siguiente localidad casi siempre es del mismo.
    setChoice({ ...EMPTY_CHOICE, PAIS: choice.PAIS })
  }

  const alreadyAdded = picked
    ? selected.some((s) => s.locality_id === picked.id && s.kind === kind)
    : false

  return (
    <div className="flex flex-col gap-3">
      {selected.length > 0 && (
        <ul className="flex flex-col gap-1.5">
          {selected.map((item, index) => (
            <li
              key={item.linkId ?? `${item.locality_id}-${item.kind}`}
              className="flex items-center gap-2 rounded-[7px] border px-2.5 py-1.5"
              style={{ background: "var(--surface-2)", borderColor: "var(--border)" }}
            >
              <MapPin className="size-3.5 shrink-0" style={{ color: "var(--faint)" }} />
              <span className="flex-1 text-[12.5px]">{item.label}</span>
              {item.kind === "MENCIONADO" && (
                <span className="text-[11px]" style={{ color: "var(--faint)" }}>
                  mencionado
                </span>
              )}
              {!disabled && (
                <button
                  type="button"
                  onClick={() => onRemove(item, index)}
                  aria-label={`Quitar ${item.label}`}
                  className="opacity-60 hover:opacity-100"
                >
                  <X className="size-3.5" />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      {!disabled && !isLoading && (error || entries.length === 0) && (
        <p
          role="alert"
          className="rounded-[7px] border px-2.5 py-2 text-[12px]"
          style={{ background: "var(--neg-soft)", borderColor: "var(--neg)", color: "var(--neg)" }}
        >
          No se pudo cargar el catálogo de lugares. Revisa que el backend esté
          arriba y que la semilla geográfica se haya aplicado al arrancar.
        </p>
      )}

      {!disabled && (
        <>
          <div className="grid gap-2 sm:grid-cols-2">
            {VISIBLE_LEVELS.map((level) => (
              <LocalityCombobox
                key={level}
                label={FIELD_LABELS[level]}
                entries={options[level]}
                selected={chosen[level]}
                disabled={isLoading}
                onSelect={(entry) => handleSelect(level, entry)}
              />
            ))}
          </div>

          <div className="flex flex-wrap items-end gap-2">
            <label className="flex flex-1 flex-col gap-1">
              <span className="text-[11.5px]" style={{ color: "var(--faint)" }}>
                Papel del lugar
              </span>
              <Select
                aria-label="Papel del lugar"
                value={kind}
                onChange={(e) => setKind(e.target.value)}
              >
                <option value="HECHO">Donde ocurrió el hecho</option>
                <option value="MENCIONADO">Solo mencionado</option>
              </Select>
            </label>
            <Button type="button" onClick={handleAdd} disabled={!picked || alreadyAdded}>
              <Plus className="size-3.5" />
              Agregar
            </Button>
          </div>

          {picked && (
            <p className="text-[11.5px]" style={{ color: "var(--faint)" }}>
              {alreadyAdded ? "Ya está en la lista: " : "Se agregará: "}
              {picked.breadcrumb}
            </p>
          )}
        </>
      )}

      {disabled && selected.length === 0 && (
        <p className="text-[12.5px]" style={{ color: "var(--faint)" }}>
          Sin lugar indicado.
        </p>
      )}
    </div>
  )
}
