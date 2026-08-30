import { LocalityPicker } from "@/components/LocalityPicker"
import { toPicked, type PickedLocality } from "@/lib/localities"
import { OdinApiError } from "@/lib/odin-api"
import {
  useArticleLocalities,
  useAddArticleLocality,
  useDeleteArticleLocality,
} from "@/lib/queries/localities"

/** Lugar de la noticia sobre un artículo ya guardado.
 *
 *  Cada alta y cada baja va contra la API en el momento, en vez de acumularse
 *  hasta un "Guardar": es el mismo gesto que el formulario que el cliente ya
 *  usa (elegir, "Agregar", y la fila aparece en la lista), y evita que se
 *  pierda trabajo si el documentalista cierra la pantalla sin guardar.
 */
export function LocalitiesCard({
  articleId,
  editable,
}: {
  articleId: number
  editable: boolean
}) {
  const { data: links, isLoading, error } = useArticleLocalities(articleId)
  const addMutation = useAddArticleLocality(articleId)
  const removeMutation = useDeleteArticleLocality(articleId)

  const selected = toPicked(links ?? [])

  const mutationError =
    addMutation.error instanceof OdinApiError
      ? addMutation.error.message
      : removeMutation.error instanceof OdinApiError
        ? removeMutation.error.message
        : null

  function handleAdd(picked: { locality_id: number; kind: string }) {
    addMutation.mutate({
      locality_id: picked.locality_id,
      kind: picked.kind,
      origin: "MANUAL",
      confidence: null,
    })
  }

  function handleRemove(picked: PickedLocality) {
    if (picked.linkId === undefined) return
    removeMutation.mutate(picked.linkId)
  }

  return (
    <div
      // Sin overflow-hidden: recortaba el desplegable del selector de
              // lugares, que se posiciona absoluto y se sale de la tarjeta.
              // Nada adentro necesita recorte por el radio.
              className="odin-glass rounded-xl border px-6 py-5"
      style={{ boxShadow: "var(--shadow-sm)" }}
    >
      <div className="mb-3 flex items-baseline gap-2">
        <h3 className="text-[15px] font-semibold">Lugar de la noticia</h3>
        <span className="font-mono text-[11px]" style={{ color: "var(--faint)" }}>
          {selected.length} {selected.length === 1 ? "indicado" : "indicados"}
        </span>
      </div>

      {error && (
        <p className="mb-2 text-[12.5px]" style={{ color: "var(--neg)" }}>
          No se pudieron cargar los lugares.
        </p>
      )}
      {mutationError && (
        <p role="alert" className="mb-2 text-[12.5px]" style={{ color: "var(--neg)" }}>
          {mutationError}
        </p>
      )}

      {isLoading ? (
        <div
          className="h-8 rounded"
          style={{ background: "var(--surface-3)", animation: "odinPulse 1.6s ease-in-out infinite" }}
        />
      ) : (
        <LocalityPicker
          selected={selected}
          onAdd={handleAdd}
          onRemove={handleRemove}
          disabled={!editable}
        />
      )}
    </div>
  )
}
