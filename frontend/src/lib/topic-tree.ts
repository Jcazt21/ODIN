import type { TopicNode } from "@/lib/odin-api"

export interface TopicRow {
  id: number
  name: string
  depth: number
  article_count: number
  parent_id: number | null
  is_active: boolean
  description: string | null
  display_order: number
  /** Todos los hijos, incluidos los inactivos ocultos por el filtro. */
  child_count: number
  /** Hijos visibles ahora mismo en el árbol. */
  has_children: boolean
}

/** Árbol -> filas planas en orden de recorrido, con la profundidad de cada una.
 *  El backend ya entrega los hermanos por `display_order`, que se respeta. */
export function flattenTopicTree(nodes: TopicNode[], depth = 0): TopicRow[] {
  return nodes.flatMap((n) => [
    {
      id: n.id,
      name: n.name,
      depth,
      article_count: n.article_count ?? 0,
      parent_id: n.parent_id ?? null,
      is_active: n.is_active ?? true,
      description: n.description ?? null,
      display_order: n.display_order ?? 0,
      child_count: n.child_count ?? 0,
      has_children: (n.children ?? []).length > 0,
    },
    ...flattenTopicTree(n.children ?? [], depth + 1),
  ])
}

/** Clave de búsqueda sin acentos ni mayúsculas. */
export function normalizeText(value: string): string {
  return value.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase().trim()
}
