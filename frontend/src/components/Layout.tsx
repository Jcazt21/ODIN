import { Outlet, useLocation, useNavigate } from "react-router-dom"
import { Nav } from "@/components/Nav"
import { SoftAurora } from "@/components/SoftAurora"
import { ErrorBoundary } from "@/components/ErrorBoundary"
import { getUsername } from "@/lib/auth"
import { softAuroraFor, SOFT_AURORA_OPACITY, type Theme } from "@/lib/aurora-config"

const NAV_ITEMS = [
  { label: "Analizar", tab: "/analyze" },
  { label: "Reportes", tab: "/reports" },
  { label: "Entidades", tab: "/entities" },
  { label: "Siglas", tab: "/aliases" },
]

// Apaga la banda de Aurora del workspace sin exponer un control en la UI: es
// lo primero que se sacrifica en equipos lentos (README §Fondo Plasma).
const WORKSPACE_AURORA_ENABLED = true

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
        // `fixed` en vez de una banda superior: la aurora queda centrada en el
        // viewport y las tarjetas translúcidas la dejan ver al hacer scroll.
        // Además es un solo canvas del tamaño de la ventana que no crece con el
        // largo de la página ni se repinta al scrollear.
        <div
          className="pointer-events-none fixed inset-0 z-0 overflow-hidden"
          style={{ opacity: SOFT_AURORA_OPACITY.workspace[theme] }}
        >
          <SoftAurora {...softAuroraFor(theme)} />
          <div
            className="absolute inset-0"
            style={{
              background:
                "radial-gradient(ellipse 85% 60% at 50% 50%, transparent 0%, var(--bg) 90%)",
            }}
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
