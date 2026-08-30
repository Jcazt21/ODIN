/** Usuario derivado del nombre: inicial del nombre + 4 primeras del apellido.
 *
 *  Es un ESPEJO de `username_from_name` en `services/user_service.py`, y existe
 *  solo para adelantar en pantalla lo que el servidor va a generar. Quien
 *  decide es el backend: además de aplicar la misma regla, resuelve los
 *  choques con un sufijo numérico que acá no se puede saber.
 */
export function usernameFromName(firstName: string, lastName: string): string {
  const first = asciiLetters(firstName.trim().split(" ")[0] ?? "")
  const last = asciiLetters(lastName)
  if (!first || !last) return ""
  return `${first[0]}${last.slice(0, 4)}`
}

/** Solo letras a-z: sin acentos, sin ñ, en minúsculas. Un usuario con acento
 *  habría que teclearlo con acento para entrar. */
function asciiLetters(value: string): string {
  return value
    .normalize("NFKD")
    .replace(/[^a-zA-Z]/g, "")
    .toLowerCase()
}
