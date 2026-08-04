// Pantalla de acceso. Solo login, sin registro ni recuperación de clave — el
// backend valida contra un usuario único definido en el entorno.
import { useState, type FormEvent } from "react"
import { Aurora } from "@/components/Aurora"
import { login, OdinApiError } from "@/lib/odin-api"

interface LoginScreenProps {
  onSuccess: (username: string) => void
  theme: "light" | "dark"
}

const AURORA_STOPS: Record<"light" | "dark", [string, string, string]> = {
  light: ["#B497CF", "#6200EE", "#B497CF"],
  dark: ["#03DAC6", "#5227FF", "#03DAC6"],
}

export function LoginScreen({ onSuccess, theme }: LoginScreenProps) {
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
    <div className="relative grid min-h-screen place-items-center" style={{ background: "var(--bg)" }}>
      <div className="pointer-events-none absolute inset-0">
        <div style={{ opacity: theme === "dark" ? 0.6 : 0.45, width: "100%", height: "100%" }}>
          <Aurora colorStops={AURORA_STOPS[theme]} speed={0.5} blend={0.6} amplitude={1.0} />
        </div>
        <div
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(ellipse 70% 60% at 50% 45%, transparent 0%, var(--bg) 78%)",
          }}
        />
      </div>

      <main className="relative z-[1] w-full max-w-[396px] px-6 pt-0 pb-10">
        <div className="mb-[26px] flex flex-col items-center gap-2 text-center">
          <h1
            className="bg-clip-text text-[44px] font-semibold text-transparent"
            style={{
              letterSpacing: "0.22em",
              paddingLeft: "0.22em",
              backgroundImage: "linear-gradient(100deg, var(--text) 20%, var(--primary) 45%, var(--text) 70%)",
              backgroundSize: "200% 100%",
              animation: "odinShimmer 6s linear infinite",
            }}
          >
            ODIN
          </h1>
          <p className="text-[13px]" style={{ color: "var(--muted-foreground)" }}>
            Monitoreo y análisis de prensa dominicana
          </p>
        </div>

        <div
          className="rounded-xl border p-[26px_24px]"
          style={{
            background: "var(--panel-strong)",
            backdropFilter: "blur(14px)",
            borderColor: "var(--border)",
            boxShadow: "var(--shadow)",
          }}
        >
          <h2 className="text-[15px] font-semibold">Iniciar sesión</h2>
          <p className="mb-5 text-[12.5px]" style={{ color: "var(--muted-foreground)" }}>
            Ingrese las credenciales del operador.
          </p>

          <form onSubmit={handleSubmit} className="flex flex-col gap-3.5">
            <div className="space-y-1.5">
              <label htmlFor="username" className="text-[12px] font-medium" style={{ color: "var(--muted-foreground)" }}>
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
                className="w-full rounded-[7px] border px-[11px] py-[9px] text-[13.5px] outline-none focus-visible:ring-2"
                style={{ background: "var(--surface-2)", borderColor: "var(--border)" }}
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="password" className="text-[12px] font-medium" style={{ color: "var(--muted-foreground)" }}>
                Contraseña
              </label>
              <input
                id="password"
                name="password"
                type="password"
                placeholder="••••••••"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-[7px] border px-[11px] py-[9px] text-[13.5px] outline-none focus-visible:ring-2"
                style={{ background: "var(--surface-2)", borderColor: "var(--border)" }}
              />
            </div>

            {error && (
              <div
                role="alert"
                className="rounded-[7px] border px-3 py-2.5 text-[12.5px]"
                style={{ background: "var(--neg-soft)", borderColor: "var(--neg)", color: "var(--neg)" }}
              >
                <strong>Error</strong> {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-[7px] px-4 py-[11px] text-[13.5px] font-semibold transition-colors disabled:opacity-60"
              style={{ background: "var(--primary)", color: "var(--accent-fg)" }}
            >
              {loading ? "Verificando…" : "Entrar"}
            </button>
          </form>

          <p
            className="mt-5 border-t pt-4 text-[11.5px] leading-[1.5]"
            style={{ borderColor: "var(--border)", color: "var(--faint)" }}
          >
            Acceso restringido a un operador. El sistema no permite crear cuentas ni recuperar
            contraseñas.
          </p>
        </div>
      </main>
    </div>
  )
}
