import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { getTopicTree, listArticles, listAuthors } from "@/lib/odin-api"

const fetchMock = vi.fn()

beforeEach(() => {
  fetchMock.mockResolvedValue(new Response(JSON.stringify({ items: [], total: 0 }), { status: 200 }))
  vi.stubGlobal("fetch", fetchMock)
})
afterEach(() => {
  fetchMock.mockReset()
  vi.unstubAllGlobals()
})

const urlOf = () => fetchMock.mock.calls[0][0] as string

describe("cliente odin-api: autores y temas", () => {
  it("listAuthors arma /api/authors con sus params", async () => {
    await listAuthors({ q: "ana", source: "listin", sort: "name", limit: 20, offset: 40 })
    const url = new URL(urlOf(), "http://x")
    expect(url.pathname).toBe("/api/authors")
    expect(Object.fromEntries(url.searchParams)).toEqual({
      q: "ana", source: "listin", sort: "name", limit: "20", offset: "40",
    })
  })

  it("listArticles acepta author y topic_id", async () => {
    await listArticles({ author: "Ana Pérez", topic_id: 4 })
    const url = new URL(urlOf(), "http://x")
    expect(url.searchParams.get("author")).toBe("Ana Pérez")
    expect(url.searchParams.get("topic_id")).toBe("4")
  })

  it("getTopicTree llama /api/topics/tree con include_inactive", async () => {
    fetchMock.mockResolvedValue(new Response("[]", { status: 200 }))
    await getTopicTree({ include_inactive: true })
    expect(urlOf()).toBe("/api/topics/tree?include_inactive=true")
    fetchMock.mockClear()
    fetchMock.mockResolvedValue(new Response("[]", { status: 200 }))
    await getTopicTree()
    expect(urlOf()).toBe("/api/topics/tree")
  })
})
