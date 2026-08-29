import type { ArticleLocality, LocalityNode, SuggestedLocality } from "@/lib/odin-api"

/** Lo que el selector necesita para mostrar una localidad ya elegida. */
export interface PickedLocality {
  locality_id: number
  kind: string
  /** Solo para mostrar: el backend recalcula el camino al guardar. */
  label: string
  /** Id del vínculo ya persistido, si lo hay. */
  linkId?: number
  /** "MANUAL" (lo eligió una persona) | "AUTO" (lo propuso el analizador y
   *  la persona lo dejó pasar). Se decide acá y viaja tal cual al POST. */
  origin?: string
  /** Confianza de la detección automática. Siempre null si origin es MANUAL. */
  confidence?: number | null
}

/** Convierte lo que devuelve la API en lo que consume el selector. */
export function toPicked(links: ArticleLocality[]): PickedLocality[] {
  return links.map((link) => ({
    locality_id: link.locality_id,
    kind: link.kind,
    label: (link.breadcrumb ?? []).map((c) => c.name).join(" › ") || link.name,
    linkId: link.id,
  }))
}

/** Sugerencias del analizador -> lo que consume el selector.
 *  Espeja `toPicked`, pero arrastra origin/confidence: si se pierden acá, el
 *  vínculo se guarda como MANUAL y deja de distinguirse lo que propuso la
 *  máquina de lo que escribió una persona. */
export function suggestedToPicked(suggestions: SuggestedLocality[]): PickedLocality[] {
  return suggestions.map((s) => ({
    locality_id: s.locality_id,
    kind: s.kind,
    label: (s.breadcrumb ?? []).map((c) => c.name).join(" › ") || s.name,
    origin: s.origin,
    confidence: s.confidence,
  }))
}

/** Minúsculas y sin acentos, para que "janico" encuentre "Jánico".
 *  Espeja `norm_key` del backend (`analysis/text_norm.py`) en lo que el
 *  buscador necesita: si las dos formas de normalizar divergen, escribir un
 *  nombre con tilde daría resultados distintos según dónde se busque. */
export function normalizeText(text: string): string {
  return text
    .normalize("NFD")
    .replace(/\p{Mn}/gu, "")
    .toLowerCase()
    .trim()
}

/** Una localidad lista para buscar, con su camino desde el país. */
export interface LocalityEntry {
  id: number
  name: string
  level: string
  /** Nombres de los ancestros, del país hacia abajo, sin incluirse. */
  ancestors: LocalityNode[]
  /** "República Dominicana › Cibao › Santiago › Tamboril" */
  breadcrumb: string
  /** Lo que se compara al teclear: el nombre y sus alias, normalizados. */
  haystack: string[]
}

export interface LocalityIndex {
  byId: Map<number, LocalityNode>
  entries: LocalityEntry[]
}

/** Recorre el árbol una vez y deja todo lo que el selector necesita:
 *  el mapa por id (para la cascada) y la lista plana con caminos y alias
 *  (para el buscador). Se hace en un solo paso porque el árbol son ~204 nodos
 *  y recorrerlo dos veces por cada tecleo sería gratuito pero innecesario. */
export function indexTree(roots: LocalityNode[]): LocalityIndex {
  const byId = new Map<number, LocalityNode>()
  const entries: LocalityEntry[] = []

  const walk = (node: LocalityNode, ancestors: LocalityNode[]) => {
    byId.set(node.id, node)
    entries.push({
      id: node.id,
      name: node.name,
      level: node.level,
      ancestors,
      breadcrumb: [...ancestors, node].map((n) => n.name).join(" › "),
      haystack: [node.name, ...(node.aliases ?? [])].map(normalizeText),
    })
    const chain = [...ancestors, node]
    for (const child of node.children ?? []) walk(child, chain)
  }

  for (const root of roots) walk(root, [])
  return { byId, entries }
}

/** Filtra por lo tecleado. Los que EMPIEZAN con el término van primero: quien
 *  escribe "san" casi siempre busca "San Cristóbal", no "Sabana Grande de
 *  Palenque", aunque las dos contengan la cadena.
 *
 *  Con el término vacío devuelve TODO el conjunto, no nada: cada campo es un
 *  desplegable escribible, y al abrirlo sin escribir tiene que mostrar sus
 *  opciones como lo haría un `<select>` normal. */
export function filterLocalities(
  entries: LocalityEntry[],
  query: string,
  limit = 300
): LocalityEntry[] {
  const q = normalizeText(query)
  if (!q) return entries.slice(0, limit)

  const starts: LocalityEntry[] = []
  const wordStarts: LocalityEntry[] = []
  for (const entry of entries) {
    if (entry.haystack.some((h) => h.startsWith(q))) starts.push(entry)
    else if (entry.haystack.some((h) => startsAWord(h, q))) wordStarts.push(entry)
  }
  return [...starts, ...wordStarts].slice(0, limit)
}

/** ¿`query` arranca alguna palabra de `text`?
 *
 *  Se exige inicio de palabra y no coincidencia en cualquier posición: con
 *  `includes`, teclear "Al" devolvía "Pepillo Salcedo" —cae dentro de
 *  "sALcedo"— y la búsqueda parecía traer cosas al azar. "Sal" sí lo encuentra.
 *
 *  Se busca la frase completa en vez de palabra por palabra para que "santa
 *  cruz" siga encontrando "Las Matas de Santa Cruz".
 */
function startsAWord(text: string, query: string): boolean {
  for (let i = text.indexOf(query); i !== -1; i = text.indexOf(query, i + 1)) {
    if (i === 0 || text[i - 1] === " " || text[i - 1] === "-") return true
  }
  return false
}

/** Las opciones de un campo: todas las localidades de ese nivel, acotadas al
 *  ancestro ya elegido si lo hay.
 *
 *  Sin ancestro devuelve el nivel COMPLETO — es lo que permite ir directo al
 *  campo de Municipio y escoger entre los 158 sin haber tocado los de arriba.
 *  El filtro por ancestro mira todo el camino, no solo el padre, así que
 *  funciona igual a través del nivel de región que el formulario no muestra. */
export function entriesAtLevel(
  entries: LocalityEntry[],
  level: string,
  ancestorId?: number
): LocalityEntry[] {
  return entries
    .filter(
      (entry) =>
        entry.level === level &&
        (ancestorId === undefined || entry.ancestors.some((a) => a.id === ancestorId))
    )
    .sort((a, b) => a.name.localeCompare(b.name, "es"))
}

/** Los cuatro niveles que el cliente ve, en el orden de su formulario.
 *  `REGION` (las 10 regiones de planificación del Decreto 710-04) existe en los
 *  datos y sirve para los reportes, pero no se muestra: su formulario tiene
 *  cuatro campos y agregarle uno quinto sería pedirle un dato que hoy no
 *  registra. El roll-up igual pasa por ese nivel. */
export const VISIBLE_LEVELS = ["PAIS", "MACRORREGION", "PROVINCIA", "MUNICIPIO"] as const
export type VisibleLevel = (typeof VISIBLE_LEVELS)[number]

/** Valor centinela de los desplegables. Reproduce el formulario que el cliente
 *  ya usa, donde "Todas" no es un campo vacío: significa que la noticia abarca
 *  todo ese nivel. */
export const ALL = "__todas__"

export const EMPTY_CHOICE: Record<VisibleLevel, string> = {
  PAIS: ALL,
  MACRORREGION: ALL,
  PROVINCIA: ALL,
  MUNICIPIO: ALL,
}

/** Deriva el estado de los cuatro desplegables desde un resultado de búsqueda.
 *  Es el camino inverso al de la cascada: elegir "Tamboril" debe dejar País,
 *  Región y Provincia ya puestos, que es justo lo que evita bajar cuatro
 *  desplegables para llegar a un municipio cuyo nombre ya se sabe. */
export function choiceFromEntry(entry: LocalityEntry): Record<VisibleLevel, string> {
  const chain = [...entry.ancestors, { id: entry.id, level: entry.level }]
  const next = { ...EMPTY_CHOICE }
  for (const level of VISIBLE_LEVELS) {
    const match = chain.find((n) => n.level === level)
    if (match) next[level] = String(match.id)
  }
  return next
}

/** Deja `level` sin elegir y limpia todos los niveles por debajo.
 *  Vaciar Provincia tiene que vaciar Municipio: el que estaba elegido ya no
 *  cuelga de nada. */
export function clearFrom(
  choice: Record<VisibleLevel, string>,
  level: VisibleLevel
): Record<VisibleLevel, string> {
  const next = { ...choice }
  const from = VISIBLE_LEVELS.indexOf(level)
  for (let i = from; i < VISIBLE_LEVELS.length; i++) next[VISIBLE_LEVELS[i]] = ALL
  return next
}
