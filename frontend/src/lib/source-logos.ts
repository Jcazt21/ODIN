/** Ícono de cada medio, por el mismo slug que usa el backend (`articles.source`,
 *  p. ej. "listin_diario"). Los archivos viven en `assets/sources/<slug>.png`;
 *  agregar un medio es soltar el PNG ahí, sin tocar este archivo.
 *
 *  El export a Word usa una copia reducida en `src/odin/exports/logos/`; un test
 *  del backend vigila que ambas carpetas cubran los mismos medios.
 */
const files = import.meta.glob<string>("@/assets/sources/*.png", {
  eager: true,
  import: "default",
})

const LOGOS: Record<string, string> = {}
for (const [path, url] of Object.entries(files)) {
  const slug = path.split("/").pop()?.replace(/\.png$/, "")
  if (slug) LOGOS[slug] = url
}

/** URL del ícono, o `undefined` si el medio no tiene (reporte manual, medio nuevo). */
export function sourceLogo(source: string | null | undefined): string | undefined {
  return source ? LOGOS[source] : undefined
}
