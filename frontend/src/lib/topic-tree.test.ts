import { describe, expect, it } from "vitest"
import { flattenTopicTree, normalizeText } from "./topic-tree"
import type { TopicNode } from "./odin-api"

const node = (id: number, name: string, article_count: number, children: TopicNode[] = []): TopicNode =>
  ({ id, name, slug: `t${id}`, parent_id: null, aliases: [], article_count, children }) as TopicNode

describe("flattenTopicTree", () => {
  it("aplana el árbol con la profundidad de cada nodo", () => {
    const rows = flattenTopicTree([node(1, "Raíz", 5, [node(2, "Hijo", 2, [node(3, "Nieto", 1)])])])
    expect(rows.map((r) => [r.id, r.depth])).toEqual([[1, 0], [2, 1], [3, 2]])
  })

  it("respeta el orden de entrada (display_order) entre hermanos", () => {
    const rows = flattenTopicTree([node(9, "Z", 0), node(1, "A", 0, [node(5, "Y", 0), node(4, "X", 0)])])
    expect(rows.map((r) => r.id)).toEqual([9, 1, 5, 4])
  })

  it("conserva article_count", () => {
    expect(flattenTopicTree([node(1, "Raíz", 7)])[0].article_count).toBe(7)
  })

  it("normalizeText ignora acentos y mayúsculas", () => {
    expect(normalizeText("Educación")).toBe("educacion")
  })
})
