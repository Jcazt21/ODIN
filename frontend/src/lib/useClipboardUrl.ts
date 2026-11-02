import { useCallback, useRef, useState } from "react"
import { isHttpUrl } from "@/lib/url"

/** Detecta una URL http(s) en el portapapeles para ofrecerla como atajo.
 *
 *  La lectura se dispara con `check()` desde un gesto del usuario (enfocar el
 *  campo): leer el portapapeles sin gesto hace que el navegador pida permiso
 *  fuera de contexto. Si el permiso se niega o la API no existe, falla en
 *  silencio y no hay sugerencia. */
export function useClipboardUrl(currentValue: string, disabled = false) {
  const [clipboardUrl, setClipboardUrl] = useState<string | null>(null)
  // Descartadas en esta sesión: no se vuelven a ofrecer.
  const dismissed = useRef(new Set<string>())
  const value = currentValue.trim()

  const check = useCallback(async () => {
    try {
      const text = (await navigator.clipboard.readText()).trim()
      setClipboardUrl(isHttpUrl(text) && !dismissed.current.has(text) ? text : null)
    } catch {
      setClipboardUrl(null)
    }
  }, [])

  const dismiss = useCallback(() => {
    setClipboardUrl((url) => {
      if (url) dismissed.current.add(url)
      return null
    })
  }, [])

  // La sugerencia sobra si el campo ya la contiene, o mientras se analiza.
  const visible = !disabled && clipboardUrl !== value ? clipboardUrl : null
  return { clipboardUrl: visible, check, dismiss }
}
