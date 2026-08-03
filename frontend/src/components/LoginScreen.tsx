// Pantalla de acceso. Mismo fondo (Aurora) y mismo lenguaje visual que el
// módulo principal: solo login, no hay registro ni recuperación de clave —
// el backend valida contra un usuario único definido en el entorno.
import { useState, type FormEvent } from "react"
import { Aurora } from "@/components/Aurora"
import { ShimmerText } from "@/components/ui/shimmer-text"
import { Input } from "@/components/ui/input"
import { InteractiveHoverButton } from "@/components/ui/interactive-hover-button"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Card, CardContent } from "@/components/ui/card"
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
          : "No se pudo conectar con la API de Odin. ¿Está corriendo en el puerto 8000?"
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="relative min-h-screen">
      <Aurora />

      <main className="mx-auto flex min-h-screen max-w-md flex-col items-center justify-center gap-8 px-4 py-16">
        <ShimmerText className="text-6xl font-bold tracking-tighter sm:text-7xl">
          ODIN
        </ShimmerText>

        <Card className="w-full">
          <CardContent className="pt-2">
            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              <div className="space-y-1.5">
                <label
                  htmlFor="username"
                  className="text-sm font-medium text-muted-foreground"
                >
                  Usuario
                </label>
                <Input
                  id="username"
                  name="username"
                  autoComplete="username"
                  autoFocus
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="h-11"
                />
              </div>

              <div className="space-y-1.5">
                <label
                  htmlFor="password"
                  className="text-sm font-medium text-muted-foreground"
                >
                  Contraseña
                </label>
                <Input
                  id="password"
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="h-11"
                />
              </div>

              {error && (
                <Alert variant="destructive">
                  <AlertTitle>No se pudo entrar</AlertTitle>
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              <InteractiveHoverButton
                type="submit"
                disabled={loading}
                loading={loading}
                text={loading ? "Entrando…" : "Entrar"}
                className="mt-1 w-full"
              />
            </form>
          </CardContent>
        </Card>

        <p className="text-center text-xs text-muted-foreground">
          Acceso restringido. El sistema no permite crear cuentas.
        </p>
      </main>
    </div>
  )
}
