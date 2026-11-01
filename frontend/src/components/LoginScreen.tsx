// Pantalla de acceso. Solo login, sin registro ni recuperación de clave — el
// backend valida contra un usuario único definido en el entorno.
import { useState, type FormEvent } from "react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { login, OdinApiError } from "@/lib/odin-api"

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
    <div className="grid min-h-screen place-items-center bg-[image:var(--shell-gradient)]">
      <main className="w-full max-w-[380px] px-6 py-10">
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-semibold tracking-tight text-[var(--sidebar-foreground)]">Odin</h1>
          <p className="mt-1 text-sm text-[var(--sidebar-foreground)]/80">Monitoreo y análisis de prensa dominicana</p>
        </div>

        <Card className="rounded-2xl p-6 shadow-[var(--shadow)]">
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
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
                className="h-10 w-full rounded-lg border bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
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
                className="h-10 w-full rounded-lg border bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </div>

            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <Button type="submit" size="lg" className="h-10 w-full" disabled={loading}>
              {loading ? "Verificando…" : "Entrar"}
            </Button>

            <p className="border-t pt-4 text-xs leading-relaxed text-muted-foreground">
              Acceso restringido a un operador. El sistema no permite crear cuentas ni recuperar contraseñas.
            </p>
          </form>
        </Card>
      </main>
    </div>
  )
}
