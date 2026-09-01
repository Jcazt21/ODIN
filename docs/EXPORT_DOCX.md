# Template .docx — Exportación de reportes ODIN

Especificación del documento que produce `src/odin/services/export_service.py`, y del
archivo que le sirve de base: `src/odin/exports/reportes-odin-template.docx`.

Esa plantilla trae dos reportes de ejemplo —uno completo y otro sin entidades ni
documentalista, que es el caso que rompe el diseño si nadie lo cuida—. Ábrela en Word,
Pages y Google Docs y compara contra lo que sale del export.

La plantilla se usa como archivo **base** del export: de ahí salen el tamaño de hoja, los márgenes, el encabezado y el pie con número de
página. Esa es la parte que se ajusta editando el .docx y no tocando Python.

La **tipografía la fija el código**, en formato directo, incluso donde además hay un estilo
de párrafo. Es deliberado: el lector de .docx de macOS ignora los estilos de párrafo con
nombre propio —el título de portada sale en Times 12— y solo respeta el formato directo.
Los estilos quedan como portadores del espaciado; la fuente, el tamaño y el color los
escribe `_run()`. Por lo mismo, la negrita solo se marca cuando la hay: apagarla escribe
`<w:b w:val="0"/>`, que ese mismo lector interpreta como negrita ENCENDIDA.

## Estructura

1. **Portada** (una sola vez): "Reportes de prensa" + una línea con el período, el conteo
   y los medios: `ODIN · 21–28 de agosto de 2026 · 12 reportes · Listín Diario, Diario Libre`.
2. **Por cada reporte**: el cuadro de ficha (tabla) y debajo el cuerpo de la nota en
   párrafos. A partir del segundo reporte, precedido de un salto de página explícito
   (`w:br w:type="page"`, no `page_break_before`: el cuadro es una tabla y no admite esa
   propiedad).
3. Encabezado "ODIN · REPORTES DE PRENSA" y número de página centrado, en cada hoja.

## Página

Letter (12240×15840 twips), márgenes de 1" en los cuatro lados, encabezado y pie a 0.5"
(720 twips) del borde.

## Estilos de párrafo (`word/styles.xml`)

| styleId | Nombre en Word | Fuente | Tamaño | Color |
|---|---|---|---|---|
| `Normal` | Normal | Georgia | 11 pt | `1A1A1A` |
| `OdinTitle` | ODIN Title | Georgia bold | 24 pt | `111111` |
| `OdinSubtitle` | ODIN Subtitle | Helvetica Neue | 9 pt, 21 pt de espacio inferior | `666666` |
| `OdinBody` | ODIN Body | Georgia | 11 pt, interlineado 1.5, 10 pt inferior | `1A1A1A` |
| `OdinHeader` | ODIN Header | Helvetica Neue, mayúsculas, tracking 30 | 8 pt | `8A8A8A` |
| `OdinFooter` | ODIN Footer | Helvetica Neue, centrado | 8 pt | `8A8A8A` |

## Cuadro de ficha

Tabla de 2 columnas de 4680 twips (total 9360 = 6.5", el ancho útil de la hoja),
`tblLayout` fijo. Marco exterior de 1 pt `C9CED3`; `insideH`/`insideV` en `none` —las
reglas internas se declaran por celda, porque la rejilla de metadatos no lleva línea en
todos los cruces. Márgenes de celda por defecto: izq/der 150 twips. Todas las filas con
`cantSplit`, para que una ficha no se parta entre dos hojas.

| Fila | Contenido | Formato |
|---|---|---|
| 1 · banda | `REPORTE 01` y el sentimiento a la derecha | relleno `22262A`, texto blanco, Helvetica Neue bold 8 / 7.5 pt, mayúsculas, tracking 24 / 28; padding 90; borde inferior 1 pt `C9CED3` |
| 2 · titular | el titular del artículo | celda combinada; Georgia bold 16 pt `141719`, interlineado 1.2; padding 170/150; borde inferior 1 pt `C9CED3` |
| 3–5 · metadatos | Medio, Sección, Publicado, Tema, Documentalista, Analizado | etiqueta Helvetica Neue bold 7 pt `7A8086` en mayúsculas con tracking 22, dato debajo en 9.5 pt `22262A`; padding 120; borde inferior 0.5 pt `E1E4E7` en las filas 3 y 4, borde izquierdo 0.5 pt `E1E4E7` en la columna derecha |
| 6 · entidades | `ENTIDADES MENCIONADAS · 4` y los nombres unidos por ` · ` | celda combinada; relleno `F4F5F6`, borde superior 1 pt `C9CED3`, padding 140; nombres en 9 pt `22262A`, interlineado 1.4 |
| 7 · fuente | `FUENTE` + la URL completa | celda combinada; borde superior 0.5 pt `DCDFE2`, padding 110; etiqueta 7 pt `9AA0A6`, URL 7.5 pt `7A8086`, sin hipervínculo azul |

Reglas de contenido:

- Valores vacíos → `—` (em dash), nunca cadena vacía ni `None`.
- `Documentalista` = `Automático` cuando no hubo revisión humana; `Analizado` queda en `—`.
- Las entidades van en el orden en que las devuelve el análisis, no alfabético.
- Sin entidades, la fila 6 se omite entera: el cuadro no puede quedar con una fila vacía.
- El color solo aparece en la banda y en la etiqueta de sentimiento; los datos descriptivos
  quedan en gris.

## Cuerpo del artículo

Fuera de la tabla, 13 pt de espacio después del cuadro, un párrafo por párrafo de la nota
en `ODIN Body`. Siempre queda al menos un párrafo detrás del cuadro: una tabla pegada al
final del cuerpo hace que Word abra el archivo con advertencia.

El cuerpo va limpio del scrape: sin el tema suelto inicial, sin el titular repetido dentro
del texto, sin párrafos duplicados (de un repetido se conserva la ÚLTIMA aparición, que es
donde arranca la nota), sin kickers de sección tipo "POLÍTICA", con las comillas rectas
convertidas en tipográficas y los espacios dobles colapsados.

## Notas

- Fuentes Georgia + Helvetica Neue (con `altName` Arial en `fontTable.xml`): presentes en
  macOS y Windows, sin sustituciones raras.
- El texto no va justificado a propósito — evita ríos de espacio cuando el ancho de columna
  cambia entre Word y Pages.
- "Semibold" no existe como peso en OOXML: los datos de la rejilla van en negrita, que a
  9.5 pt junto a una etiqueta de 7 pt en gris da el contraste que pide el diseño.
- Word valida el ORDEN de los hijos de cada elemento de propiedades (`w:tcPr`, `w:rPr`…).
  Como el export escribe ese OOXML a mano —python-docx no expone rellenos, bordes por
  celda, `cantSplit` ni tracking—, hay una prueba que lo verifica
  (`TestOpensWithoutWarnings` en `tests/api/test_export_template.py`).
