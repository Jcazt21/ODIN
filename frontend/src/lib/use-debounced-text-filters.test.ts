import { describe, expect, it, vi, afterEach } from "vitest"
import { act, renderHook } from "@testing-library/react"
import { useDebouncedTextFilters } from "@/lib/use-debounced-text-filters"
import type { ArticleListParams } from "@/lib/odin-api"

afterEach(() => {
  vi.useRealTimers()
})

describe("useDebouncedTextFilters", () => {
  it("espera antes de propagar un tema recién escrito", () => {
    /* El tema es una caja de texto: sin debounce, cada tecla de "policía" son
       siete peticiones al listado. */
    vi.useFakeTimers()
    const { result, rerender } = renderHook(
      ({ filters }: { filters: ArticleListParams }) => useDebouncedTextFilters(filters),
      { initialProps: { filters: {} as ArticleListParams } }
    )

    rerender({ filters: { topic: "poli" } })
    expect(result.current.topic).toBeUndefined()

    act(() => void vi.advanceTimersByTime(300))
    expect(result.current.topic).toBe("poli")
  })

  it("propaga de inmediato lo que no es texto libre", () => {
    /* Contraste que da sentido al test de arriba: un clic en un desplegable no
       debe heredar la espera del texto. */
    vi.useFakeTimers()
    const { result, rerender } = renderHook(
      ({ filters }: { filters: ArticleListParams }) => useDebouncedTextFilters(filters),
      { initialProps: { filters: {} as ArticleListParams } }
    )

    rerender({ filters: { source: "listin_diario" } })

    expect(result.current.source).toBe("listin_diario")
  })
})
