import { useQuery } from "@tanstack/react-query"
import { getMe } from "@/lib/odin-api"
import { getToken } from "@/lib/auth"

/** Valida el token guardado contra /api/auth/me al abrir la aplicación. Sin
 *  token no dispara la llamada; un 401 ya limpia la sesión por dentro de
 *  request() y dispara AUTH_EXPIRED_EVENT (ver App), así que acá basta con no
 *  reintentar sobre un error de auth. */
export function useMe() {
  return useQuery({
    queryKey: ["auth", "me"],
    queryFn: getMe,
    enabled: Boolean(getToken()),
    retry: false,
    staleTime: Infinity,
  })
}
