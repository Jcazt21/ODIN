import { Outlet, useLocation } from "react-router-dom"
import { Nav } from "@/components/Nav"
import { ErrorBoundary } from "@/components/ErrorBoundary"
import { getRole, getUsername } from "@/lib/auth"
import type { Theme } from "@/lib/theme"

/** Contexto que Layout pasa a las páginas hijas vía <Outlet context>. */
export interface WorkspaceOutletContext {
  theme: Theme
  onToggleTheme: () => void
}

interface LayoutProps {
  onLogout: () => void
  theme: Theme
  onToggleTheme: () => void
}

/** Todas las rutas se alinean a la izquierda y usan el ancho de la hoja. Los
    formularios largos conservan un tope de lectura, pero sin centrarse. */
function widthFor(pathname: string): string {
  return pathname === "/reports/new" || pathname === "/settings" ? "max-w-[880px]" : ""
}

export function Layout({ onLogout, theme, onToggleTheme }: LayoutProps) {
  const location = useLocation()

  return (
    <div className="min-h-screen bg-[image:var(--shell-gradient)] lg:grid lg:h-screen lg:grid-cols-[16rem_minmax(0,1fr)] lg:gap-4 lg:overflow-hidden lg:p-4 lg:pb-0">
      <Nav username={getUsername()} role={getRole()} theme={theme} onToggleTheme={onToggleTheme} onLogout={onLogout} />
      {/* La hoja es el contenedor con scroll en escritorio; en móvil scrollea la ventana. */}
      <main
        tabIndex={0}
        aria-label="Contenido"
        className="min-h-[calc(100vh-3.5rem)] bg-background outline-none focus-visible:ring-3 focus-visible:ring-ring/50 lg:h-full lg:min-h-0 lg:overflow-y-auto lg:rounded-t-[28px] lg:bg-[var(--sheet)]"
      >
        <div className={`flex w-full flex-col gap-6 px-6 pt-8 pb-20 lg:px-10 ${widthFor(location.pathname)}`}>
          <ErrorBoundary resetKey={location.pathname}>
            {/* key: cada ruta remonta el contenedor y vuelve a correr la entrada. */}
            <div key={location.pathname} className="odin-enter flex flex-col gap-6">
              <Outlet context={{ theme, onToggleTheme } satisfies WorkspaceOutletContext} />
            </div>
          </ErrorBoundary>
        </div>
      </main>
    </div>
  )
}
