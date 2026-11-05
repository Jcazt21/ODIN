import { describe, expect, it, vi, beforeEach } from "vitest"
import { renderHook, waitFor, act } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import type { ReactNode } from "react"
import * as odinApi from "@/lib/odin-api"
import { topicKeys, useCreateTopic, useDeleteTopic, useUpdateTopic } from "@/lib/queries/topics"

vi.mock("@/lib/odin-api", async () => {
  const actual = await vi.importActual<typeof odinApi>("@/lib/odin-api")
  return { ...actual, createTopic: vi.fn(), updateTopic: vi.fn(), deleteTopic: vi.fn() }
})

function setup() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const invalidate = vi.spyOn(queryClient, "invalidateQueries")
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return { invalidate, wrapper }
}

beforeEach(() => vi.resetAllMocks())

describe("hooks de mutación de temas", () => {
  it("invalida el árbol tras crear", async () => {
    vi.mocked(odinApi.createTopic).mockResolvedValue({} as never)
    const { invalidate, wrapper } = setup()
    const { result } = renderHook(() => useCreateTopic(), { wrapper })
    await act(() => result.current.mutateAsync({ name: "A" }))
    expect(invalidate).toHaveBeenCalledWith({ queryKey: topicKeys.all })
  })

  it("invalida el árbol tras actualizar", async () => {
    vi.mocked(odinApi.updateTopic).mockResolvedValue({} as never)
    const { invalidate, wrapper } = setup()
    const { result } = renderHook(() => useUpdateTopic(), { wrapper })
    await act(() => result.current.mutateAsync({ id: 3, payload: { is_active: false } }))
    expect(odinApi.updateTopic).toHaveBeenCalledWith(3, { is_active: false })
    expect(invalidate).toHaveBeenCalledWith({ queryKey: topicKeys.all })
  })

  it("invalida el árbol tras borrar", async () => {
    vi.mocked(odinApi.deleteTopic).mockResolvedValue(undefined)
    const { invalidate, wrapper } = setup()
    const { result } = renderHook(() => useDeleteTopic(), { wrapper })
    await act(() => result.current.mutateAsync(3))
    expect(odinApi.deleteTopic).toHaveBeenCalledWith(3)
    expect(invalidate).toHaveBeenCalledWith({ queryKey: topicKeys.all })
  })

  it("no invalida si falla y expone el error", async () => {
    vi.mocked(odinApi.createTopic).mockRejectedValue(new odinApi.OdinApiError("ya existe"))
    const { invalidate, wrapper } = setup()
    const { result } = renderHook(() => useCreateTopic(), { wrapper })
    await act(() => result.current.mutateAsync({ name: "A" }).catch(() => undefined))
    await waitFor(() => expect(result.current.error?.message).toBe("ya existe"))
    expect(invalidate).not.toHaveBeenCalled()
  })
})
