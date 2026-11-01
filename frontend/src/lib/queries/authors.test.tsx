import { renderHook, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import type { ReactNode } from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { authorKeys, useAuthorArticles } from "./authors"
import { topicKeys, useTopicArticles } from "./topics"

const listArticles = vi.fn()
vi.mock("@/lib/odin-api", () => ({
  listArticles: (...a: unknown[]) => listArticles(...a),
  listAuthors: vi.fn(),
  getTopicTree: vi.fn(),
}))

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

beforeEach(() => {
  listArticles.mockReset()
  listArticles.mockResolvedValue({ items: [], total: 0, limit: 10, offset: 0 })
})

describe("hooks de artículos por fila", () => {
  it("useAuthorArticles no llama a la API hasta enabled", async () => {
    const { rerender } = renderHook(({ on }) => useAuthorArticles("Ana", on), { wrapper, initialProps: { on: false } })
    expect(listArticles).not.toHaveBeenCalled()
    rerender({ on: true })
    await waitFor(() => expect(listArticles).toHaveBeenCalledWith(expect.objectContaining({ author: "Ana" })))
  })

  it("useTopicArticles no llama a la API hasta enabled", async () => {
    const { rerender } = renderHook(({ on }) => useTopicArticles(4, on), { wrapper, initialProps: { on: false } })
    expect(listArticles).not.toHaveBeenCalled()
    rerender({ on: true })
    await waitFor(() => expect(listArticles).toHaveBeenCalledWith(expect.objectContaining({ topic_id: 4 })))
  })

  it("las claves incluyen sus params", () => {
    expect(authorKeys.articles("Ana", 10)).not.toEqual(authorKeys.articles("Luis", 10))
    expect(topicKeys.articles(1, 10)).not.toEqual(topicKeys.articles(1, 20))
  })
})
