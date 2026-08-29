import { useOutletContext } from "react-router-dom"
import { UsersCard } from "@/components/UsersCard"
import { useMe } from "@/lib/queries/auth"
import { SkyToggle } from "@/components/ui/sky-toggle"
import type { WorkspaceOutletContext } from "@/components/Layout"

/**
 * Ajustes del workspace: el alta de usuarios (solo admin) y el tema. El layout
 * de fila (etiqueta + control a la derecha) está pensado para crecer con más
 * filas de preferencias sin rediseñar la tarjeta.
 */
export function SettingsPage() {
  const { theme, onToggleTheme } = useOutletContext<WorkspaceOutletContext>()

  // De la query y no de `getRole()`: ese lee localStorage durante el render y
  // no es reactivo, mientras que `setRole` corre en un useEffect de App, o sea
  // después. Quien cargaba la página estando acá se dibujaba sin rol y no se
  // volvía a dibujar cuando llegaba: la tarjeta no aparecía hasta navegar
  // afuera y volver. El rol solo decide qué se dibuja; quien autoriza de
  // verdad sigue siendo require_admin en el backend.
  const { data: me } = useMe()
  const isAdmin = me?.role === "admin"

  return (
    <div>
      <header>
        <h1 className="text-[19px] font-semibold">Ajustes</h1>
        <p className="mt-0.5 text-[12.5px]" style={{ color: "var(--faint)" }}>
          Usuarios del sistema y preferencias de la interfaz.
        </p>
      </header>

      {isAdmin && (
        <div className="mt-4">
          <UsersCard />
        </div>
      )}

      <div className="odin-glass mt-4 rounded-xl border" style={{ boxShadow: "var(--shadow)" }}>
        <div className="flex items-center justify-between gap-4 p-4">
          <div>
            <div className="text-[14px] font-medium">Tema</div>
            <div className="mt-0.5 text-[12px]" style={{ color: "var(--faint)" }}>
              Apariencia clara u oscura de la aplicación.
            </div>
          </div>

          <SkyToggle
            checked={theme === "dark"}
            onChange={onToggleTheme}
            aria-label={theme === "dark" ? "Cambiar a tema claro" : "Cambiar a tema oscuro"}
          />
        </div>
      </div>
    </div>
  )
}
