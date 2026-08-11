import { useEffect, useState } from "react"
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"
import { Layout } from "@/components/Layout"
import { ProtectedRoute } from "@/components/ProtectedRoute"
import { DialogProvider } from "@/lib/dialog"
import { LoginPage } from "@/pages/LoginPage"
import { AnalyzePage } from "@/pages/AnalyzePage"
import { ReportsPage } from "@/pages/ReportsPage"
import { ReportDetailPage } from "@/pages/ReportDetailPage"
import { EntitiesPage } from "@/pages/EntitiesPage"
import { AliasesPage } from "@/pages/AliasesPage"
import { SettingsPage } from "@/pages/SettingsPage"
import { useMe } from "@/lib/queries/auth"
import { AUTH_EXPIRED_EVENT, clearSession, getToken, getUsername } from "@/lib/auth"

type Theme = "light" | "dark"
const THEME_KEY = "odin.theme"

function getInitialTheme(): Theme {
  try {
    const stored = localStorage.getItem(THEME_KEY)
    if (stored === "light" || stored === "dark") return stored
  } catch {
    // localStorage no disponible: usar el default
  }
  return "light"
}

/**
 * Puerta de entrada: sin sesión válida no se monta nada del workspace.
 *
 * Al abrir la aplicación con un token guardado lo validamos contra
 * /api/auth/me (useMe) — puede haber vencido o haber sido firmado con otro
 * secreto (la API reinició sin ODIN_JWT_SECRET). Mientras tanto se muestra
 * una pantalla en blanco (sin Aurora: evita montar/desmontar WebGL en una
 * vista transitoria) para no parpadear entre login y workspace.
 */
function App() {
  const [username, setUsername] = useState<string | null>(() =>
    getToken() ? getUsername() : null
  )
  const [theme, setTheme] = useState<Theme>(getInitialTheme)
  const meQuery = useMe()

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try {
      localStorage.setItem(THEME_KEY, theme)
    } catch {
      // localStorage no disponible: el tema no persiste entre sesiones
    }
  }, [theme])

  function toggleTheme() {
    setTheme((t) => (t === "dark" ? "light" : "dark"))
  }

  // Cualquier 401 en cualquier llamada devuelve al login.
  useEffect(() => {
    const onExpired = () => setUsername(null)
    window.addEventListener(AUTH_EXPIRED_EVENT, onExpired)
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired)
  }, [])

  useEffect(() => {
    if (meQuery.data) setUsername(meQuery.data.username)
    else if (meQuery.isError) setUsername(null) // el 401 ya limpió el token
  }, [meQuery.data, meQuery.isError])

  function handleLogout() {
    clearSession()
    setUsername(null)
  }

  const checking = Boolean(getToken()) && meQuery.isPending

  if (checking) {
    return <div className="min-h-screen" style={{ background: "var(--bg)" }} />
  }

  return (
    <DialogProvider>
      <BrowserRouter>
        <Routes>
          <Route
            path="/login"
            element={<LoginPage authed={Boolean(username)} theme={theme} onSuccess={setUsername} />}
          />
          <Route
            element={
              <ProtectedRoute authed={Boolean(username)}>
                <Layout onLogout={handleLogout} theme={theme} onToggleTheme={toggleTheme} />
              </ProtectedRoute>
            }
          >
            <Route path="/analyze" element={<AnalyzePage />} />
            <Route path="/reports" element={<ReportsPage />} />
            <Route path="/reports/:id" element={<ReportDetailPage />} />
            <Route path="/entities" element={<EntitiesPage />} />
            <Route path="/aliases" element={<AliasesPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/" element={<Navigate to="/analyze" replace />} />
          </Route>
          <Route path="*" element={<Navigate to={username ? "/analyze" : "/login"} replace />} />
        </Routes>
      </BrowserRouter>
    </DialogProvider>
  )
}

export default App
