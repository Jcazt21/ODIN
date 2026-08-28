import { useState } from "react"
import { useOutletContext } from "react-router-dom"
import { LocalityPicker } from "@/components/LocalityPicker"
import { UsersCard } from "@/components/UsersCard"
import { useMe } from "@/lib/queries/auth"
import { SkyToggle } from "@/components/ui/sky-toggle"
import type { WorkspaceOutletContext } from "@/components/Layout"
import type { PickedLocality } from "@/lib/localities"

/**
 * Ajustes del workspace. Por ahora solo expone el tema; el layout de fila
 * (etiqueta + control a la derecha) está pensado para crecer con más filas de
 * preferencias sin rediseñar la tarjeta.
 */
export function SettingsPage() {
  const { theme, onToggleTheme } = useOutletContext<WorkspaceOutletContext>()
  // Banco de pruebas del selector de lugar: estado local, nada se guarda.
  const [demo, setDemo] = useState<PickedLocality[]>([])

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
          Preferencias de la interfaz.
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

      <div className="odin-glass mt-4 rounded-xl border" style={{ boxShadow: "var(--shadow)" }}>
        <div className="border-b p-4" style={{ borderColor: "var(--border)" }}>
          <div className="text-[14px] font-medium">Lugar de la noticia — prueba</div>
          <div className="mt-0.5 text-[12px]" style={{ color: "var(--faint)" }}>
            Escribe un municipio y los demás campos se completan solos. Nada de lo
            que agregues aquí se guarda: es solo para probar el selector.
          </div>
        </div>

        <div className="p-4">
          <LocalityPicker
            selected={demo}
            onAdd={(picked) =>
              setDemo((current) => [
                ...current,
                { locality_id: picked.locality_id, kind: picked.kind, label: picked.label },
              ])
            }
            onRemove={(_, index) =>
              setDemo((current) => current.filter((_, i) => i !== index))
            }
          />

          {demo.length > 0 && (
            <pre
              className="mt-3 overflow-auto rounded-[7px] border p-2.5 text-[11px]"
              style={{ background: "var(--surface-2)", borderColor: "var(--border)" }}
            >
              {JSON.stringify(
                demo.map(({ locality_id, kind }) => ({ locality_id, kind })),
                null,
                2
              )}
            </pre>
          )}
        </div>
      </div>
    </div>
  )
}
