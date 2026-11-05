// Pantalla de acceso. Solo login, sin registro ni recuperación de clave: las
// cuentas las crea y restablece un administrador. Pintura a la izquierda
// (oculta en pantallas angostas), formulario a la derecha.
import { useState, type FormEvent } from "react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { login, OdinApiError } from "@/lib/odin-api"
import paintingUrl from "@/assets/login/pintura-verde.webp"

interface LoginScreenProps {
  onSuccess: (username: string) => void
}

export function LoginScreen({ onSuccess }: LoginScreenProps) {
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (loading || !username.trim() || !password) return
    setLoading(true)
    setError(null)
    try {
      const session = await login(username.trim(), password)
      onSuccess(session.username)
    } catch (err) {
      setPassword("")
      setError(
        err instanceof OdinApiError
          ? err.message
          : "No se pudo conectar con la API de Odin. ¿Está corriendo en el puerto 8001?"
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="grid min-h-screen bg-[var(--bg)] lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
      <aside className="relative m-3 hidden overflow-hidden rounded-2xl lg:block">
        <img
          src={paintingUrl}
          alt=""
          aria-hidden="true"
          width={1400}
          height={2100}
          decoding="async"
          className="absolute inset-0 size-full object-cover"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/55 via-transparent to-transparent" />
        <div className="absolute inset-x-0 bottom-0 p-8 text-white">
          <p className="font-serif text-4xl font-medium tracking-tight">Odin</p>
          <p className="mt-1 text-sm text-white/85">Monitoreo y análisis de prensa dominicana</p>
        </div>
      </aside>

      <main className="grid place-items-center px-6 py-10">
        <div className="w-full max-w-[300px]">
          <p className="mb-6 text-center font-serif text-2xl font-medium tracking-tight lg:hidden">Odin</p>
          <h1 className="text-center text-xl font-semibold tracking-tight">Iniciar sesión</h1>
          <p className="mt-2 text-center text-sm text-muted-foreground">Ingresa con tu cuenta de Odin</p>

          <form onSubmit={handleSubmit} className="mt-8 flex flex-col gap-4">
            <div className="space-y-1.5">
              <label htmlFor="username" className="text-sm font-medium">
                Usuario
              </label>
              <input
                id="username"
                name="username"
                autoComplete="username"
                autoFocus
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="h-10 w-full rounded-full border bg-card px-4 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="password" className="text-sm font-medium">
                Contraseña
              </label>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="h-10 w-full rounded-full border bg-card px-4 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </div>

            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <Button type="submit" size="lg" className="mt-2 h-10 w-full rounded-full" disabled={loading}>
              {loading ? "Verificando…" : "Entrar"}
            </Button>
          </form>

          <p className="mt-6 text-center text-xs leading-relaxed text-muted-foreground">
            Acceso restringido. Si no tienes cuenta o olvidaste tu contraseña, pídele a un administrador que la cree o
            la restablezca.
          </p>
        </div>
      </main>
    </div>
  )
}
