import { act, renderHook } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { useClipboardUrl } from "./useClipboardUrl"

function mockClipboard(readText: () => Promise<string>) {
  Object.defineProperty(navigator, "clipboard", { value: { readText }, configurable: true })
}

afterEach(() => {
  Reflect.deleteProperty(navigator, "clipboard")
})

describe("useClipboardUrl", () => {
  it("ofrece una URL http(s) del portapapeles", async () => {
    mockClipboard(async () => " https://www.diariolibre.com/nota ")
    const { result } = renderHook(() => useClipboardUrl(""))
    await act(() => result.current.check())
    expect(result.current.clipboardUrl).toBe("https://www.diariolibre.com/nota")
  })

  it("ignora texto que no es URL", async () => {
    mockClipboard(async () => "hola mundo")
    const { result } = renderHook(() => useClipboardUrl(""))
    await act(() => result.current.check())
    expect(result.current.clipboardUrl).toBeNull()
  })

  it("no la ofrece si el campo ya la tiene ni mientras se analiza", async () => {
    mockClipboard(async () => "https://a.com/x")
    const { result, rerender } = renderHook(({ v, d }) => useClipboardUrl(v, d), {
      initialProps: { v: "", d: false },
    })
    await act(() => result.current.check())
    expect(result.current.clipboardUrl).toBe("https://a.com/x")
    rerender({ v: "https://a.com/x", d: false })
    expect(result.current.clipboardUrl).toBeNull()
    rerender({ v: "", d: true })
    expect(result.current.clipboardUrl).toBeNull()
  })

  it("descartar la recuerda durante la sesión", async () => {
    mockClipboard(async () => "https://a.com/x")
    const { result } = renderHook(() => useClipboardUrl(""))
    await act(() => result.current.check())
    act(() => result.current.dismiss())
    expect(result.current.clipboardUrl).toBeNull()
    await act(() => result.current.check())
    expect(result.current.clipboardUrl).toBeNull()
  })

  it("permiso denegado o API ausente no rompe", async () => {
    mockClipboard(vi.fn().mockRejectedValue(new DOMException("denied", "NotAllowedError")))
    const { result } = renderHook(() => useClipboardUrl(""))
    await act(() => result.current.check())
    expect(result.current.clipboardUrl).toBeNull()
    Reflect.deleteProperty(navigator, "clipboard")
    await act(() => result.current.check())
    expect(result.current.clipboardUrl).toBeNull()
  })
})
