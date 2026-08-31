import { useEffect, useState } from "react"
import type { ArticleListParams } from "@/lib/odin-api"

/** Debounce solo de los campos de texto libre (q, entity, topic): clicks en selects,
 *  fechas, orden o paginación deben reflejarse de inmediato — antes heredaban
 *  los mismos 300ms de espera del texto y se sentían lentos.
 *
 *  En archivo propio y no dentro de ReportsPage: exportar algo que no es un
 *  componente desde una página rompe Fast Refresh. Aparte se prueba aislado,
 *  que conviene porque qué campo espera y cuál no tiene consecuencia visible
 *  (una petición por tecla si se olvida sumar un campo de texto nuevo). */
export function useDebouncedTextFilters(filters: ArticleListParams): ArticleListParams {
  const [debounced, setDebounced] = useState(filters)
  useEffect(() => {
    const textChanged =
      filters.q !== debounced.q ||
      filters.entity !== debounced.entity ||
      filters.topic !== debounced.topic
    if (!textChanged) {
      setDebounced(filters)
      return
    }
    const t = setTimeout(() => setDebounced(filters), 300)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters])
  return debounced
}
