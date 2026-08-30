import { useEffect, useState } from "react"
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"
import { Layout } from "@/components/Layout"
import { ProtectedRoute } from "@/components/ProtectedRoute"
import { DialogProvider } from "@/lib/dialog"
import { LoginPage } from "@/pages/LoginPage"
import { AnalyzePage } from "@/pages/AnalyzePage"
import { ReportsPage } from "@/pages/ReportsPage"
import { ReportDetailPage } from "@/pages/ReportDetailPage"
import { NewReportPage } from "@/pages/NewReportPage"
import { ChangePasswordPage } from "@/pages/ChangePasswordPage"
import { EntitiesPage } from "@/pages/EntitiesPage"
import { AliasesPage } from "@/pages/AliasesPage"
import { DocumentalistsPage } from "@/pages/DocumentalistsPage"
import { SettingsPage } from "@/pages/SettingsPage"
import { useMe } from "@/lib/queries/auth"
import { AUTH_EXPIRED_EVENT, clearSession, getToken, getUsername, setRole } from "@/lib/auth"

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
    if (meQuery.data) {
      setUsername(meQuery.data.username)
      // El rol solo decide qué se dibuja en esta pestaña; quien autoriza de
      // verdad es require_admin en el backend.
      setRole(meQuery.data.role ?? null)
    } else if (meQuery.isError) {
      setUsername(null) // el 401 ya limpió el token (y el rol, vía clearSession)
    }
  }, [meQuery.data, meQuery.isError])

  function handleLogout() {
    clearSession()
    setUsername(null)
  }

  const checking = Boolean(getToken()) && meQuery.isPending

  if (checking) {
    return <div className="min-h-screen" style={{ background: "var(--bg)" }} />
  }

  // Entró con el PIN de primer acceso: nada más se dibuja hasta que elija su
  // contraseña. No es solo cortesía de interfaz — con el portón encendido el
  // backend responde 403 a todo lo demás, así que cualquier otra pantalla
  // estaría rota. Al terminar se refresca `me` para que el portón se apague
  // con el token nuevo que dejó `changePassword`.
  if (meQuery.data?.must_change_password) {
    return <ChangePasswordPage onDone={() => meQuery.refetch()} />
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
            {/* Antes de "/reports/:id": si no, "new" se leería como un id. */}
            <Route path="/reports/new" element={<NewReportPage />} />
            <Route path="/reports/:id" element={<ReportDetailPage />} />
            <Route path="/entities" element={<EntitiesPage />} />
            <Route path="/aliases" element={<AliasesPage />} />
            <Route path="/documentalists" element={<DocumentalistsPage />} />
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
