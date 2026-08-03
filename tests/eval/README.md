# Golden set de evaluación

Corpus de artículos reales con entidades y sentimiento etiquetados a mano,
para medir objetivamente qué tan bien funciona un `Analyzer` (local o
Gemini) — en vez de confiar en los porcentajes de precisión de `README.md`,
que hoy no tienen ningún artefacto que los respalde (`task.md` §2.4).

## Estado actual: 7 artículos (punto de partida, no el objetivo)

`golden_set.jsonl` tiene **7 filas**, una por cada artículo que hoy vive en
`odin.db` (el corpus real y completo del proyecto en este momento). El
objetivo de `task.md` §12 P0#7 es **150-300 artículos**; llegar ahí es
trabajo de etiquetado humano que no se puede improvisar en una sola sesión —
requiere leer cada artículo con cuidado y decidir, para cada entidad, si el
tono es POS/NEG/NEU. Este archivo es la base sobre la que crecer, con el
formato y las herramientas (`scripts/evaluate.py`) ya funcionando.

Las etiquetas de estas 7 filas se hicieron leyendo el texto completo de cada
artículo. No sustituyen una revisión humana independiente — antes de
confiar en ellas para decisiones de producto, alguien del equipo debería
releerlas. El campo `notes` de cada fila documenta los casos ambiguos y por
qué se decidió así.

## Formato (JSONL, un artículo por línea)

```json
{
  "id": "odin-db-001",
  "source": "diario_libre",
  "url": "https://...",
  "title": "...",
  "body": "...",
  "overall_sentiment": "NEU",
  "entities_exhaustive": true,
  "entities": [
    {"name": "Dirección General de Impuestos Internos", "type": "ORG", "sentiment_toward": "NEU"}
  ],
  "notes": "por qué se etiquetó así, casos límite"
}
```

- `overall_sentiment` / `sentiment_toward`: `"POS" | "NEG" | "NEU"`.
- `entities`: la lista **canónica** correcta (el nombre que debería quedar
  en la BD después de canonicalizar, no necesariamente el string exacto que
  extraería un NER). `scripts/evaluate.py` empareja por nombre normalizado
  con contención de palabras (mismo criterio que
  `analysis/canonicalize.py`), así que "Impuestos Internos" cuenta como
  acierto contra el gold "Dirección General de Impuestos Internos".
- `sentiment_toward` puede ser `null` cuando no hay forma razonable de
  decidirlo a mano; esas entidades cuentan para precision/recall pero no
  para la accuracy de sentimiento.
- `entities_exhaustive` (default `true`): dice si la lista de entidades del
  artículo está **completa**. Cuando es `false` (ver `odin-db-005`, un
  artículo-trivia con ~54 nombres de presidentes dominicanos, del cual solo
  se etiquetó un subconjunto representativo), `scripts/evaluate.py` **no**
  cuenta como falso positivo ninguna entidad que el analizador encuentre y
  no esté en el gold — solo se evalúa recall y sentimiento sobre las
  entidades sí etiquetadas. Sin este flag, un artículo parcialmente
  etiquetado penalizaría injustamente a un analizador que en realidad
  acertó.

## Cómo correr la evaluación

```bash
python scripts/evaluate.py                       # LocalAnalyzer (gratis)
python scripts/evaluate.py --out reporte.json     # + reporte JSON
python scripts/evaluate.py --analyzer gemini      # llamadas FACTURADAS — ver CLAUDE.md, no correr sin querer
```

## Cómo agregar más artículos

1. Guardar el artículo (vía la app o `sqlite3 odin.db`) y copiar
   `source, url, title, body`.
2. Leer el cuerpo completo y decidir `overall_sentiment` y, por cada
   entidad real (PERSON/ORG), su `type` y `sentiment_toward`. Usar el
   nombre **canónico** (el que debería quedar tras `canonicalize.py`).
3. Si no se etiquetaron TODAS las entidades del artículo, marcar
   `"entities_exhaustive": false`.
4. Anotar en `notes` cualquier caso límite y por qué se decidió así — es lo
   que le permite a quien revise después entender el criterio sin releer
   todo el artículo.
5. Repartir entre fuentes y secciones variadas (no solo `diario_libre`): hoy
   el golden set no cubre la mayoría de las 8 fuentes, ver `task.md` §2.4.
