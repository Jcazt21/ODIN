import { useQuery } from "@tanstack/react-query"
import { getMe } from "@/lib/odin-api"
import { getToken } from "@/lib/auth"

/** Valida el token guardado contra /api/auth/me al abrir la aplicación. Sin
 *  token no dispara la llamada; un 401 ya limpia la sesión por dentro de
 *  request() y dispara AUTH_EXPIRED_EVENT (ver App), así que acá basta con no
 *  reintentar sobre un error de auth. */
export function useMe() {
  const token = getToken()
  return useQuery({
    // El token forma parte de la clave: sin él, cerrar sesión y entrar con
    // otra cuenta reusaba la entrada cacheada de la anterior. Como es una SPA
    // no hay recarga que vacíe la memoria, y con staleTime infinito React
    // Query no volvía a preguntar — el `me` del usuario previo se servía al
    // siguiente, y con él su `must_change_password`.
    queryKey: ["auth", "me", token],
    queryFn: getMe,
    enabled: Boolean(token),
    retry: false,
    staleTime: Infinity,
  })
}
