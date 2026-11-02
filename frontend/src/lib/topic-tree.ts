import type { TopicNode } from "@/lib/odin-api"

export interface TopicRow {
  id: number
  name: string
  depth: number
  article_count: number
}

/** Árbol -> filas planas en orden de recorrido, con la profundidad de cada una.
 *  El backend ya entrega los hermanos por `display_order`, que se respeta. */
export function flattenTopicTree(nodes: TopicNode[], depth = 0): TopicRow[] {
  return nodes.flatMap((n) => [
    { id: n.id, name: n.name, depth, article_count: n.article_count ?? 0 },
    ...flattenTopicTree(n.children ?? [], depth + 1),
  ])
}

/** Clave de búsqueda sin acentos ni mayúsculas. */
export function normalizeText(value: string): string {
  return value.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase().trim()
}
