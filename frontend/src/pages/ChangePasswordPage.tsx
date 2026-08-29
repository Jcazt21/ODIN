import { useId, useState } from "react"
import { useMutation } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { changePassword, MIN_PASSWORD_LENGTH, OdinApiError } from "@/lib/odin-api"

/** Cambio obligatorio tras entrar con el PIN de primer acceso.
 *
 *  Es una pantalla que BLOQUEA: sin nav, sin cancelar y sin ruta que la
 *  esquive. No es celo de interfaz — el backend cierra todas las demás rutas
 *  con 403 mientras el portón esté encendido, así que ofrecer una salida solo
 *  llevaría a una aplicación que no responde.
 *
 *  La validación de largo se repite acá y en el servidor a propósito: en
 *  pantalla es para no hacer ir y volver por un error evidente; la que manda,
 *  y la única que no se puede esquivar, es la del servidor.
 */
export function ChangePasswordPage({ onDone }: { onDone: () => void }) {
  const passwordId = useId()
  const repeatId = useId()
  const [password, setPassword] = useState("")
  const [repeat, setRepeat] = useState("")
  const [localError, setLocalError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: (value: string) => changePassword(value),
    onSuccess: onDone,
  })

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (password.length < MIN_PASSWORD_LENGTH) {
      setLocalError(`La contraseña debe tener al menos ${MIN_PASSWORD_LENGTH} caracteres.`)
      return
    }
    if (password !== repeat) {
      setLocalError("Las dos contraseñas no coinciden.")
      return
    }
    setLocalError(null)
    mutation.mutate(password)
  }

  const serverError = mutation.error instanceof OdinApiError ? mutation.error.message : null

  return (
    <div
      className="flex min-h-screen items-center justify-center px-4"
      style={{ background: "var(--bg)" }}
    >
      <form
        onSubmit={handleSubmit}
        className="odin-glass w-full max-w-sm rounded-xl border px-6 py-6"
        style={{ boxShadow: "var(--shadow-sm)" }}
      >
        <h1 className="text-[17px] font-semibold">Elegí tu contraseña</h1>
        <p className="mt-1 mb-5 text-[13px]" style={{ color: "var(--muted-foreground)" }}>
          Entraste con un PIN de un solo uso. Para seguir, definí una contraseña
          propia de al menos {MIN_PASSWORD_LENGTH} caracteres.
        </p>

        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <label htmlFor={passwordId} className="text-[12px]" style={{ color: "var(--muted-foreground)" }}>
              Nueva contraseña
            </label>
            <input
              id={passwordId}
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => {
                setPassword(e.target.value)
                setLocalError(null)
              }}
              className="h-9 w-full rounded-[7px] border px-3 text-[13px] outline-none"
              style={{ background: "var(--surface-2)", borderColor: "var(--border)" }}
            />
          </div>

          <div className="flex flex-col gap-1">
            <label htmlFor={repeatId} className="text-[12px]" style={{ color: "var(--muted-foreground)" }}>
              Repetila
            </label>
            <input
              id={repeatId}
              type="password"
              autoComplete="new-password"
              value={repeat}
              onChange={(e) => {
                setRepeat(e.target.value)
                setLocalError(null)
              }}
              className="h-9 w-full rounded-[7px] border px-3 text-[13px] outline-none"
              style={{ background: "var(--surface-2)", borderColor: "var(--border)" }}
            />
          </div>
        </div>

        {(localError || serverError) && (
          <p className="mt-3 text-[12px]" style={{ color: "var(--neg)" }} role="alert">
            {localError ?? serverError}
          </p>
        )}

        <Button type="submit" className="mt-5 w-full" disabled={mutation.isPending}>
          {mutation.isPending ? "Cambiando…" : "Cambiar contraseña"}
        </Button>
      </form>
    </div>
  )
}
