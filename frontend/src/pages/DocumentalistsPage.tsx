import { useMe } from "@/lib/queries/auth"
import { formatDay } from "@/lib/format"
import {
  useDocumentalists,
  useDocumentalistKpi,
  useUpdateDocumentalist,
} from "@/lib/queries/documentalists"

/**
 * Documentalistas y su trabajo.
 *
 * El resumen de volumen solo lo ve un admin: el backend responde 403 al resto,
 * y aquí ni siquiera se pide (`enabled`), para no provocar un error visible en
 * la consola de quien no tiene por qué verlo.
 */
export function DocumentalistsPage() {
  // De la query y no de `isAdmin()`: ese lee localStorage durante el render
  // y no es reactivo, mientras que `setRole` corre en un useEffect de App.
  // Cargar la página acá directamente dejaba el KPI sin pedir. Quien
  // autoriza sigue siendo require_admin en el backend.
  const { data: me } = useMe()
  const admin = me?.role === "admin"
  const { data: documentalists } = useDocumentalists()
  const { data: kpi } = useDocumentalistKpi(undefined, undefined, admin)
  const updateMutation = useUpdateDocumentalist()

  const workById = new Map((kpi ?? []).map((row) => [row.documentalist_id, row]))

  return (
    <div>
      <header>
        <h1 className="text-[19px] font-semibold">Documentalistas</h1>
        <p className="mt-0.5 text-[12.5px]" style={{ color: "var(--faint)" }}>
          Quién captura los reportes{admin ? " y cuánto lleva cada uno" : ""}.
        </p>
      </header>

      <div
        className="odin-glass mt-4 overflow-x-auto rounded-xl border"
        style={{ boxShadow: "var(--shadow)" }}
      >
        <table className="w-full text-[12.5px]">
          <thead>
            <tr style={{ color: "var(--faint)" }}>
              <th className="px-3 py-2 text-left font-medium">Nombre</th>
              <th className="px-3 py-2 text-left font-medium">Usuario</th>
              <th className="px-3 py-2 text-left font-medium">Rol</th>
              {admin && <th className="px-3 py-2 text-right font-medium">Reportes</th>}
              {admin && <th className="px-3 py-2 text-right font-medium">Días activos</th>}
              {admin && <th className="px-3 py-2 text-right font-medium">Último</th>}
              <th className="px-3 py-2 text-right font-medium">Estado</th>
            </tr>
          </thead>
          <tbody>
            {(documentalists ?? []).map((a) => {
              const work = workById.get(a.id)
              return (
                <tr key={a.id} className="border-t" style={{ borderColor: "var(--border)" }}>
                  <td className="px-3 py-2">{a.display_name}</td>
                  <td className="px-3 py-2" style={{ color: "var(--faint)" }}>
                    {a.username}
                  </td>
                  <td className="px-3 py-2" style={{ color: "var(--faint)" }}>
                    {a.role}
                  </td>
                  {admin && (
                    <td className="px-3 py-2 text-right font-mono">{work?.articles ?? 0}</td>
                  )}
                  {admin && (
                    <td className="px-3 py-2 text-right font-mono">{work?.active_days ?? 0}</td>
                  )}
                  {admin && (
                    <td className="px-3 py-2 text-right font-mono">
                      {formatDay(work?.last_on)}
                    </td>
                  )}
                  <td className="px-3 py-2 text-right">
                    <button
                      type="button"
                      onClick={() =>
                        updateMutation.mutate({ id: a.id, payload: { is_active: !a.is_active } })
                      }
                      className="text-[12px] underline-offset-2 hover:underline"
                      style={{ color: a.is_active ? "var(--faint)" : "var(--neg)" }}
                    >
                      {a.is_active ? "Activo" : "Inactivo"}
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {admin && (
        <p className="mt-4 text-[12.5px]" style={{ color: "var(--faint)" }}>
          Los usuarios se dan de alta en Ajustes, donde se les genera el PIN de
          primer acceso. Acá quedan el listado y el trabajo de cada uno.
        </p>
      )}
    </div>
  )
}
