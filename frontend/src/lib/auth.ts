import { queryClient } from "@/lib/query-client"

// Sesión del operador: el JWT que devuelve /api/auth/login vive en
// localStorage y viaja en la cabecera Authorization de cada llamada.
//
// No hay registro de usuarios: el backend valida contra credenciales del
// entorno (ver auth.py). Aquí solo guardamos el token y avisamos al resto de
// la aplicación cuando deja de servir.

const TOKEN_KEY = "odin.token"
const USER_KEY = "odin.user"
const ROLE_KEY = "odin:role"

/** Se dispara cuando la API responde 401: App vuelve a la pantalla de login. */
export const AUTH_EXPIRED_EVENT = "odin:auth-expired"

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function getUsername(): string | null {
  try {
    return localStorage.getItem(USER_KEY)
  } catch {
    return null
  }
}

export function setSession(token: string, username: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token)
    localStorage.setItem(USER_KEY, username)
  } catch {
    // Modo privado o storage lleno: la sesión durará lo que dure la pestaña.
  }
}

export function clearSession(): void {
  try {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    localStorage.removeItem(ROLE_KEY)
  } catch {
    // nada que limpiar
  }
  // La caché en memoria se va con la sesión. Es una SPA: cerrar sesión no
  // recarga la página, así que sin esto quien entra después hereda los
  // reportes, el listado de usuarios y el KPI del anterior.
  queryClient.clear()
}

export function notifyAuthExpired(): void {
  window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT))
}

export function getRole(): string | null {
  try {
    return localStorage.getItem(ROLE_KEY)
  } catch {
    // Modo privado o almacenamiento bloqueado: sin rol, la UI de admin
    // simplemente no se muestra. El backend sigue siendo quien decide.
    return null
  }
}

export function setRole(role: string | null): void {
  try {
    if (role) localStorage.setItem(ROLE_KEY, role)
    else localStorage.removeItem(ROLE_KEY)
  } catch {
    // ignorado a propósito: el rol es una conveniencia de la interfaz
  }
}

export function isAdmin(): boolean {
  return getRole() === "admin"
}
