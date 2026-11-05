import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import {
  createTopic,
  deleteTopic,
  getTopicTree,
  listArticles,
  listAuthors,
  updateTopic,
} from "@/lib/odin-api"
import { OdinApiError } from "@/lib/api-error"

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

describe("cliente odin-api: CRUD de temas", () => {
  it("createTopic envía POST con payload", async () => {
    fetchMock.mockResolvedValue(new Response("{}", { status: 201 }))
    await createTopic({ name: "Salud", parent_id: null })
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe("/api/topics")
    expect(init.method).toBe("POST")
    expect(JSON.parse(init.body)).toEqual({ name: "Salud", parent_id: null })
  })

  it("updateTopic envía PUT a /api/topics/{id}", async () => {
    fetchMock.mockResolvedValue(new Response("{}", { status: 200 }))
    await updateTopic(7, { is_active: false })
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe("/api/topics/7")
    expect(init.method).toBe("PUT")
    expect(JSON.parse(init.body)).toEqual({ is_active: false })
  })

  it("deleteTopic resuelve en 204", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }))
    await expect(deleteTopic(7)).resolves.toBeUndefined()
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe("/api/topics/7")
    expect(init.method).toBe("DELETE")
  })

  it("updateTopic propaga OdinApiError con el detail del 409", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: "'Salud' ya existe bajo ese tema padre." }), { status: 409 })
    )
    const err = await updateTopic(7, { name: "Salud" }).catch((e) => e)
    expect(err).toBeInstanceOf(OdinApiError)
    expect(err.message).toBe("'Salud' ya existe bajo ese tema padre.")
  })
})
