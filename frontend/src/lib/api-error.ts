/** Error de la API de Odin: un 4xx conocido con `detail` legible.
 *
 *  Vive en su propio módulo, y no en `odin-api.ts`, para no encadenar
 *  `auth.ts` → `query-client.ts` → `odin-api.ts` → `auth.ts`. Ese ciclo hacía
 *  que el grafo de módulos quedara a medio inicializar según quién se cargara
 *  primero. Como hoja del grafo, este archivo no importa nada del proyecto.
 */
export class OdinApiError extends Error {}
