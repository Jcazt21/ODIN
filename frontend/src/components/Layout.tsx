import { Outlet, useLocation, useNavigate } from "react-router-dom"
import { Nav } from "@/components/Nav"
import { Aurora } from "@/components/Aurora"
import { ErrorBoundary } from "@/components/ErrorBoundary"
import { getUsername } from "@/lib/auth"

type Theme = "light" | "dark"

const NAV_ITEMS = [
  { label: "Analizar", tab: "/analyze" },
  { label: "Reportes", tab: "/reports" },
  { label: "Entidades", tab: "/entities" },
  { label: "Siglas", tab: "/aliases" },
]

// Apaga la banda de Aurora del workspace sin exponer un control en la UI: es
// lo primero que se sacrifica en equipos lentos (README §Fondo Plasma).
const WORKSPACE_AURORA_ENABLED = true

const AURORA_STOPS: Record<Theme, [string, string, string]> = {
  light: ["#B497CF", "#6200EE", "#B497CF"],
  dark: ["#03DAC6", "#5227FF", "#03DAC6"],
}

interface LayoutProps {
  onLogout: () => void
  theme: Theme
  onToggleTheme: () => void
}

export function Layout({ onLogout, theme, onToggleTheme }: LayoutProps) {
  const location = useLocation()
  const navigate = useNavigate()
  const activeTab = NAV_ITEMS.find((item) => location.pathname.startsWith(item.tab))?.tab ?? "/analyze"

  return (
    <div className="relative min-h-screen" style={{ background: "var(--bg)" }}>
      {WORKSPACE_AURORA_ENABLED && (
        <div
          className="pointer-events-none absolute inset-x-0 top-0 z-0 h-[420px] overflow-hidden"
          style={{ opacity: theme === "dark" ? 0.5 : 0.35 }}
        >
          <Aurora colorStops={AURORA_STOPS[theme]} speed={0.4} blend={0.55} amplitude={0.9} />
          <div
            className="absolute inset-0"
            style={{ background: "linear-gradient(to bottom, transparent 0%, var(--bg) 88%)" }}
          />
        </div>
      )}

      <div className="relative z-[1] mx-auto max-w-[1180px] px-6 pt-[22px] pb-20">
        <Nav
          items={NAV_ITEMS}
          activeTab={activeTab}
          onTabChange={(tab) => navigate(tab)}
          username={getUsername()}
          onLogout={onLogout}
          theme={theme}
          onToggleTheme={onToggleTheme}
        />

        <main className="mt-[22px] flex flex-col gap-[22px]">
          <ErrorBoundary resetKey={location.pathname}>
            <Outlet />
          </ErrorBoundary>
        </main>
      </div>
    </div>
  )
}
