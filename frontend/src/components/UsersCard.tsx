import { useId, useState } from "react"
import { KeyRound } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Select } from "@/components/ui/select"
import {
  useDocumentalists,
  useCreateDocumentalist,
  useResetDocumentalistPin,
} from "@/lib/queries/documentalists"
import { OdinApiError, type DocumentalistCreated } from "@/lib/odin-api"
import { usernameFromName } from "@/lib/username"

/** Alta de usuarios con PIN de primer acceso (solo admin).
 *
 *  Es el ÚNICO lugar donde se crean usuarios. La pantalla de Documentalistas
 *  quedó con el listado y el KPI: dos formularios de alta terminan divergiendo,
 *  y el día que uno valide algo que el otro no, el agujero entra por el que se
 *  olvidó.
 *
 *  El PIN se muestra una sola vez porque se guarda hasheado — no hay forma de
 *  volver a leerlo, solo de generar otro.
 */
export function UsersCard() {
  const firstNameId = useId()
  const lastNameId = useId()
  const roleId = useId()

  const { data: users } = useDocumentalists()
  const createMutation = useCreateDocumentalist()
  const resetMutation = useResetDocumentalistPin()

  const [form, setForm] = useState({ first_name: "", last_name: "", role: "documentalista" })
  const preview = usernameFromName(form.first_name, form.last_name)
  const [revealed, setRevealed] = useState<DocumentalistCreated | null>(null)

  function handleCreate(event: React.FormEvent) {
    event.preventDefault()
    if (!form.first_name.trim() || !form.last_name.trim()) return
    createMutation.mutate(
      {
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        role: form.role,
      },
      {
        onSuccess: (created) => {
          setRevealed(created as DocumentalistCreated)
          setForm({ first_name: "", last_name: "", role: "documentalista" })
        },
      }
    )
  }

  const error =
    createMutation.error instanceof OdinApiError
      ? createMutation.error.message
      : resetMutation.error instanceof OdinApiError
        ? resetMutation.error.message
        : null

  return (
    <div
      className="odin-glass overflow-hidden rounded-xl border px-6 py-5"
      style={{ boxShadow: "var(--shadow-sm)" }}
    >
      <h3 className="text-[15px] font-semibold">Usuarios</h3>
      <p className="mt-1 mb-4 text-[12.5px]" style={{ color: "var(--muted-foreground)" }}>
        Al crear a alguien se genera un PIN de 4 dígitos para su primer acceso.
        Al entrar con él, el sistema le pide que elija su propia contraseña.
      </p>

      {revealed && (
        <div
          className="mb-4 rounded-lg border px-4 py-3"
          style={{ borderColor: "var(--border)", background: "var(--surface-2)" }}
        >
          <p className="text-[12.5px]" style={{ color: "var(--muted-foreground)" }}>
            PIN de {revealed.display_name || revealed.username}
          </p>
          <p className="font-mono text-[26px] tracking-[0.3em]">{revealed.pin}</p>
          <p className="mt-1 text-[11.5px]" style={{ color: "var(--faint)" }}>
            Anotalo y entregáselo: no se vuelve a mostrar. Si se pierde, regenerá uno nuevo.
          </p>
          <button
            type="button"
            className="mt-2 text-[12px] underline"
            onClick={() => setRevealed(null)}
          >
            Listo, ya lo anoté
          </button>
        </div>
      )}

      <form onSubmit={handleCreate} className="mb-5 flex flex-col gap-3">
        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1">
            <label htmlFor={firstNameId} className="text-[12px]" style={{ color: "var(--muted-foreground)" }}>
              Nombre
            </label>
            <input
              id={firstNameId}
              value={form.first_name}
              onChange={(e) => setForm({ ...form, first_name: e.target.value })}
              className="h-9 w-full rounded-[7px] border px-3 text-[13px] outline-none"
              style={{ background: "var(--surface-2)", borderColor: "var(--border)" }}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor={lastNameId} className="text-[12px]" style={{ color: "var(--muted-foreground)" }}>
              Apellido
            </label>
            <input
              id={lastNameId}
              value={form.last_name}
              onChange={(e) => setForm({ ...form, last_name: e.target.value })}
              className="h-9 w-full rounded-[7px] border px-3 text-[13px] outline-none"
              style={{ background: "var(--surface-2)", borderColor: "var(--border)" }}
            />
          </div>
        </div>

        {preview && (
          <p className="text-[12px]" style={{ color: "var(--muted-foreground)" }}>
            Usuario:{" "}
            <span className="font-mono" style={{ color: "var(--foreground)" }}>
              {preview}
            </span>{" "}
            <span style={{ color: "var(--faint)" }}>
              — si ya existe, se le agrega un número.
            </span>
          </p>
        )}

        <div className="flex items-end gap-3">
          <div className="flex flex-1 flex-col gap-1">
            <label htmlFor={roleId} className="text-[12px]" style={{ color: "var(--muted-foreground)" }}>
              Rol
            </label>
            <Select
              id={roleId}
              value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value })}
            >
              <option value="documentalista">Documentalista</option>
              <option value="admin">Administrador</option>
            </Select>
          </div>
          <Button type="submit" disabled={createMutation.isPending}>
            {createMutation.isPending ? "Creando…" : "Crear usuario"}
          </Button>
        </div>
      </form>

      {error && (
        <p className="mb-3 text-[12px]" style={{ color: "var(--neg)" }} role="alert">
          {error}
        </p>
      )}

      <ul className="flex flex-col gap-1">
        {(users ?? []).map((u) => (
          <li
            key={u.id}
            className="flex items-center justify-between rounded-[7px] px-2 py-1.5 text-[13px]"
          >
            <span>
              {u.display_name}{" "}
              <span className="font-mono text-[11.5px]" style={{ color: "var(--faint)" }}>
                {u.username} · {u.role}
              </span>
            </span>
            <Button
              type="button"
              variant="ghost"
              disabled={resetMutation.isPending}
              onClick={() =>
                resetMutation.mutate(u.id, { onSuccess: (created) => setRevealed(created) })
              }
            >
              <KeyRound className="mr-1 h-3.5 w-3.5" />
              Regenerar PIN
            </Button>
          </li>
        ))}
      </ul>
    </div>
  )
}
