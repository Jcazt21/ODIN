# LocalAnalyzer Accuracy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cerrar la parte alcanzable de la brecha entre `LocalAnalyzer`
(spaCy + pysentimiento, gratis) y los analizadores LLM (Groq/Gemini) en las
dos cosas que SÍ intenta hacer — extracción de entidades y sentimiento —
corrigiendo 4 mecanismos de fallo concretos, medidos y reproducidos
directamente contra el golden set real de 42 artículos, y dejando fijada
una nueva línea base para comparar contra la de 2026-08-13.

**Architecture:** Cuatro fixes independientes y de bajo riesgo sobre
`src/odin/analysis/local_analyzer.py` y `src/odin/analysis/sentiment_lexicon.py`
(sin nuevas dependencias, sin tocar la BD en tiempo de análisis): (1) dejar
de filtrar "Gobierno" como ORG genérico, (2) elegir el nombre de display
más completo en vez del más repetido al fusionar alias, (3) resolver siglas
dominicanas conocidas contra el catálogo estático ya curado
(`db/seed_aliases.py`, sin abrir sesión de BD), y (4) atenuar hacia NEU las
frases con negación/desmentido explícito, que hoy el modelo base de
pysentimiento ignora. Cada fix se valida contra el golden set real antes de
darlo por bueno — no se ajusta ningún umbral a ciegas.

**Tech Stack:** Python 3.13, spaCy `es_core_news_lg`, pysentimiento, pytest.
Sin dependencias nuevas.

**Spec:** No hay PRD para este proyecto (decisión tomada en una sesión
anterior — ver `docs/planning/task.md`/`docs/planning/conflicts.md` como
fuente de verdad). Este plan argumenta directamente desde evidencia medida
en esta sesión: `tests/eval/golden_set.jsonl` (42 artículos reales,
etiquetados a mano) y `tests/eval/baselines/2026-08-13-local.json` (reporte
real de `scripts/evaluate.py --analyzer local` contra ese golden set), más
lectura directa del código fuente de `src/odin/analysis/local_analyzer.py`,
`src/odin/analysis/sentiment_lexicon.py`, `src/odin/analysis/canonicalize.py`
y `src/odin/db/seed_aliases.py`.

## Estado: NO ejecutado

Este plan quedó completo y auto-contenido pero sin ejecutar (decisión
tomada al revisarlo: costo estimado ~550-650k tokens para las 5 tareas vía
`subagent-driven-development`, ver desglose al final de este documento). Si
se retoma, la relación costo/beneficio más alta está en las Tareas 1+2
(~140k tokens) — el resto puede ejecutarse después, por separado.

## Contexto — qué está roto, medido, no adivinado

Línea base actual (`docs/PRECISION.md` §4, `tests/eval/baselines/2026-08-13-local.json`,
42 artículos):

| Métrica                      | Valor                                           |
| ---------------------------- | ----------------------------------------------- |
| Entidades F1 (overall)       | 74.0% (P 75.2%, R 72.8%)                        |
| Entidades F1 — PERSON        | **94.9%** (P 92.3%, R 97.6%)                    |
| Entidades F1 — ORG           | **52.6%** (P 56.0%, R 49.6%, tp=65 fp=51 fn=66) |
| `overall_sentiment` accuracy | 59.5% (17/42 artículos mal clasificados)        |
| `sentiment_toward` accuracy  | 59.9%                                           |

La brecha ORG vs. PERSON (52.6% vs. 94.9%) es la señal más grande y más
barata de cerrar. Se investigaron los 66 falsos negativos y 51 falsos
positivos de ORG leyendo el golden set y **re-corriendo `LocalAnalyzer` en
vivo contra 8 artículos reales** (no son hipótesis, son reproducciones
directas). Causas dominantes, en orden de impacto medido:

1. **`_GENERIC_STATE_ORGS` filtra "Gobierno" siempre** — 12 de 131
   entidades ORG etiquetadas a mano en el golden set son literalmente
   `"Gobierno"` (9.2% del total). Verificado en vivo: 7/7 artículos donde el
   gold trae "Gobierno" nunca lo extraen (`local_analyzer.py:59-61`). Esto
   solo explica **≥18% de los 66 falsos negativos de ORG**, sin ninguna
   ambigüedad de por medio — es un filtro de código, no un límite del modelo.
2. **`_merge_aliases` elige el nombre a mostrar por conteo, no por
   completitud** (`local_analyzer.py:510`, `display.most_common(1)`): en
   `odin-db-008/013/037/038` el artículo menciona "PLD" más veces que
   "Partido de la Liberación Dominicana", así que el resultado final es
   "PLD" — que el emparejador del evaluador (`_names_match`, sin
   conocimiento de siglas) nunca hace calzar contra el gold. Confirmado en
   vivo en las 4 artículos: produce "PLD" como único nombre, aunque el
   nombre completo también apareciera y se hubiera fusionado correctamente
   por dentro.
3. **Ningún mecanismo resuelve una sigla cuando el cuerpo NUNCA escribe el
   nombre completo** (`odin-db-008`, `odin-db-012`: el artículo solo dice
   "PLD", nunca "Partido de la Liberación Dominicana") — esto no lo puede
   arreglar ninguna fusión intra-artículo, hace falta un catálogo externo.
   **Ya existe uno**: `src/odin/db/seed_aliases.py` (`SEED_ALIASES`, lista
   estática en memoria, sin BD) ya trae `PLD`, `PRM`, `CNM`, `SCJ`, `JCE`,
   `OPRET`, `DGII` y decenas más — pero **`LocalAnalyzer` nunca lo consulta**
   (solo lo usa `canonicalize.py`, aplicado río abajo al guardar en BD, y
   `scripts/evaluate.py` llama a `analyzer.analyze()` directo, sin pasar por
   esa capa).
4. **El modelo base de pysentimiento no distingue negación** —
   `overall_sentiment` tiene 59.5% de accuracy con **17/42 artículos mal
   clasificados**, y el patrón se repite: en `odin-db-024`/`odin-db-025`
   (gold NEU) el artículo cita a un funcionario **negando** que haya
   apagones ("No hay apagones, no podemos hablar de apagones sino de
   sobrecarga"), pero cada frase con "apagón"/"avería" puntúa NEG 0.63-0.96
   **a pesar de la negación explícita** — confirmado leyendo las
   probabilidades reales por frase. Ninguna de esas palabras está en
   `sentiment_lexicon.py` (no es el boost de Odin fallando, es el modelo
   base de pysentimiento, entrenado en tuits generales, sin manejo de
   negación).

**Fuera de alcance, deliberadamente** — no incluido en este plan:

- **`framing`/`sentiment_basis`/`facts_sentiment`/`quoted_sentiment`/`media_stance`/`content_flags`**:
  `LocalAnalyzer` nunca los toca (confirmado leyendo `base.py:43-71` y
  `local_analyzer.py` completo) porque exigen comprensión de texto, no
  extracción — es un techo estructural de un sistema heurístico, no un bug
  tuneable. "Acercarlo a Groq/Gemini" en este plan significa mejorar lo que
  SÍ intenta (entidades, `overall_sentiment`, `sentiment_toward`), no
  fingir que puede hacer juicio editorial.
- **El clúster más grande de errores de `overall_sentiment`** (14 de los 17
  artículos mal clasificados: `overall_sentiment` POS/NEG del gold cae a
  NEU en artículos largos con mucho contenido administrativo/narrativo
  diluyendo el sentimiento real — `odin-db-002/003/014/019/027`, etc.) **no
  tiene un fix seguro y barato identificado.** Se investigó un filtro de
  "frases tabulares" (líneas de precios como en `odin-db-019`) por densidad
  de dígitos, y **se descartó tras medirlo contra el texto real**: una
  frase típica de la tabla de precios de `odin-db-019` da ~10-16% de
  dígitos, casi igual que una frase narrativa normal con un par de números
  (~9.6%) — el umbral no discrimina de forma confiable y arriesga romper
  frases narrativas legítimas. Ponderar el lead más que el resto del
  cuerpo es la idea con más potencial, pero rediseñar `_aggregate` con solo
  42 artículos de referencia es exactamente el tipo de "ajuste a ciegas"
  que este proyecto ya decidió evitar (`docs/planning/task.md` §2.4). Se
  documenta como pendiente en la Tarea 5, no se implementa aquí.

## Global Constraints

- **Validar cada fix contra el golden set real** (`tests/eval/golden_set.jsonl`,
  42 artículos) corriendo `scripts/evaluate.py --analyzer local` y
  comparando contra `tests/eval/baselines/2026-08-13-local.json` — nunca
  ajustar un umbral o una lista sin medir el efecto real.
- **Sin llamadas a Gemini/Groq**: todo este plan es local y gratis; no hay
  necesidad ni permiso de tocar `gemini_analyzer.py`/`groq_analyzer.py`
  (CLAUDE.md sigue aplicando de todas formas).
- **Sin nueva dependencia de BD en tiempo de análisis**: el catálogo de
  siglas se consume como lista estática en memoria (`SEED_ALIASES`), nunca
  vía `db.aliases.resolve()` (que exige sesión de BD) — mantiene
  `scripts/evaluate.py` determinista y sin depender de qué haya en una BD
  externa en el momento de correrlo.
- **`_LOCAL_ANALYZER_VERSION` sube cuando cambia una heurística que afecta
  el resultado** (convención ya documentada en
  `local_analyzer.py:44-49`) — de `"6"` a `"7"` al final de este plan.
- Los tests que dependen de spaCy real siguen el patrón ya establecido en
  `tests/analysis/test_local_analyzer.py` (fixture `nlp` de alcance
  `module`, modelo real, sin mockear) — no introducir un patrón de mocking
  nuevo.

---

## Task 1: No filtrar "Gobierno" como ORG genérico

**Files:**

- Modify: `src/odin/analysis/local_analyzer.py:54-61`
- Test: `tests/analysis/test_local_analyzer.py`

**Interfaces:**

- Consumes: nada nuevo.
- Produces: nada que otra tarea consuma — cambio autocontenido.

- [x] **Step 1: Escribir los tests que fallan**

> **Ejecutado 2026-08-14** — desviación respecto al texto literal de abajo:
> la frase de ejemplo del test positivo (`"El Gobierno anunció..."`) etiqueta
> "Gobierno" como LOC en `es_core_news_lg`, no ORG — nunca habría ejercido el
> fix. Se usó en su lugar `"La Fuerza del Pueblo presentó sus críticas y
propuestas frente al Gobierno."` (misma construcción adversarial aplicada
> también al test negativo de "Estado", que tenía el mismo problema).
> Verificado en vivo contra spaCy antes de aceptar la desviación; ver
> `git log` (commits `0c62077`, `ebe72b0`) para el texto final real.

Agregar a `tests/analysis/test_local_analyzer.py`, después de la clase
`TestVenueHeuristics` (termina en la línea 107) y antes de
`TestEntitySentimentBoost`:

```python
class TestGenericStateOrgFilter:
    """`_GENERIC_STATE_ORGS` filtra "República"/"Estado"/etc. sueltos, pero
    NO "Gobierno" — 12 de 131 entidades ORG del golden set son literalmente
    "Gobierno" (tests/eval/golden_set.jsonl) y el filtro viejo las perdía
    todas (verificado en vivo, ver local_analyzer.py:54-61)."""

    @staticmethod
    def _org_names(nlp, text: str) -> set[str]:
        doc = nlp(text)
        sentences = _Sentences.from_doc(doc)
        probas_by_index = [None for _ in sentences.texts]
        entities = LocalAnalyzer()._entities(doc, probas_by_index, sentences)
        return {e.name for e in entities if e.type == "ORG"}

    def test_gobierno_is_extracted_as_an_org_entity(self, nlp):
        orgs = self._org_names(
            nlp, "El Gobierno anunció un nuevo programa de subsidios para el sector agrícola."
        )
        assert "Gobierno" in orgs

    def test_bare_estado_is_still_filtered(self, nlp):
        orgs = self._org_names(
            nlp, "El Estado debe garantizar los derechos de todos los ciudadanos."
        )
        assert "Estado" not in orgs
```

Esto usa `_Sentences` y `LocalAnalyzer`, ya importados en el archivo — no
hace falta agregar imports.

- [x] **Step 2: Confirmar que fallan**

Run: `pytest tests/analysis/test_local_analyzer.py::TestGenericStateOrgFilter -v`
Expected: FAIL en `test_gobierno_is_extracted_as_an_org_entity` — "Gobierno"
no aparece en `orgs` porque el filtro actual lo descarta.

- [x] **Step 3: Quitar "gobierno" del filtro**

Reemplazar el bloque en `src/odin/analysis/local_analyzer.py` (líneas 54-61):

```python
# palabras de estado/país/gobierno genéricas: spaCy a veces las etiqueta como
# ORG cuando aparecen solas y capitalizadas ("presidente... de la República"),
# pero no son el nombre propio de ninguna organización real. Solo se filtran
# cuando son la entidad COMPLETA (p.ej. "República Dominicana" sigue
# reconociéndose porque ahí "República" no es el span entero).
_GENERIC_STATE_ORGS = {
    "republica", "estado", "gobierno", "nacion", "pais", "administracion",
}
```

por:

```python
# palabras de estado/país genéricas: spaCy a veces las etiqueta como ORG
# cuando aparecen solas y capitalizadas ("presidente... de la República"),
# pero no son el nombre propio de ninguna organización real. Solo se filtran
# cuando son la entidad COMPLETA (p.ej. "República Dominicana" sigue
# reconociéndose porque ahí "República" no es el span entero).
#
# "gobierno" NO está en esta lista a propósito (medido contra el golden set,
# tests/eval/golden_set.jsonl: 12 de 131 entidades ORG etiquetadas a mano
# son literalmente "Gobierno" — 9.2% del total — y el filtro viejo las
# perdía las 7 verificadas en vivo). A diferencia de "República"/"Estado"
# sueltos, "el Gobierno" SÍ es como la prensa dominicana nombra al actor
# político de turno ("el Gobierno sostiene que...", "acusó al Gobierno de
# ..."), no una referencia vaga al país.
_GENERIC_STATE_ORGS = {
    "republica", "estado", "nacion", "pais", "administracion",
}
```

- [x] **Step 4: Confirmar que pasan**

Run: `pytest tests/analysis/test_local_analyzer.py -v`
Expected: PASS — todos, incluidos los nuevos.

- [x] **Step 5: Commit**

```bash
git add src/odin/analysis/local_analyzer.py tests/analysis/test_local_analyzer.py
git commit -m "fix: stop filtering 'Gobierno' as a generic state ORG"
```

> **Estado real:** commit `0c62077`. Un fix round posterior (revisión de
> rama completa) corrigió dos hallazgos Important — el test negativo de
> "Estado" también resultó vacío por el mismo problema de etiquetado LOC, y
> un comentario en el sitio del filtro (`local_analyzer.py:469-472`) seguía
> listando "Gobierno" como filtrado — commit `ebe72b0`. Mergeado a `main`
> (fast-forward) con el suite completo en verde (264 tests).

---

## Task 2: Elegir el nombre de display más completo, no el más repetido

**Files:**

- Modify: `src/odin/analysis/local_analyzer.py:186-207` (agregar función
  cerca de `_extraction_confidence`), `:510` (usarla en `_entities`)
- Test: `tests/analysis/test_local_analyzer.py`

**Interfaces:**

- Consumes: nada nuevo.
- Produces: `_best_display_name(display: Counter[str]) -> str` — función
  libre a nivel de módulo, sin dependencias de spaCy. No la consume ninguna
  otra tarea de este plan, pero queda disponible para reutilizar.

- [x] **Step 1: Escribir los tests que fallan**

Agregar a `tests/analysis/test_local_analyzer.py`. Primero, ampliar el
import de `odin.analysis.local_analyzer` (líneas 15-22) agregando
`_best_display_name`:

```python
from odin.analysis.local_analyzer import (
    LocalAnalyzer,
    _best_display_name,
    _extraction_confidence,
    _is_named_after_place,
    _norm_key,
    _preceded_by_venue_noun,
    _Sentences,
)
```

Y agregar `from collections import Counter` junto al resto de imports del
archivo (después de `import pytest`, línea 11-13):

```python
from collections import Counter

import pytest
```

Nueva clase de test, después de `TestExtractionConfidence` (termina en la
línea 69) y antes de `TestVenueHeuristics`:

```python
class TestBestDisplayName:
    def test_prefers_full_name_over_more_frequent_acronym(self):
        display = Counter({"PLD": 5, "Partido de la Liberación Dominicana": 1})
        assert _best_display_name(display) == "Partido de la Liberación Dominicana"

    def test_falls_back_to_most_common_on_tied_word_count(self):
        display = Counter({"Luis Abinader": 1, "Rafael Abinader": 3})
        assert _best_display_name(display) == "Rafael Abinader"

    def test_single_candidate_is_returned_unchanged(self):
        display = Counter({"MINERD": 3})
        assert _best_display_name(display) == "MINERD"
```

- [x] **Step 2: Confirmar que fallan**

Run: `pytest tests/analysis/test_local_analyzer.py::TestBestDisplayName -v`
Expected: FAIL — `ImportError: cannot import name '_best_display_name'`.

- [ ] **Step 3: Implementar la función y usarla**

En `src/odin/analysis/local_analyzer.py`, agregar esta función justo
después de `_extraction_confidence` (que termina en la línea 207) y antes
de `@dataclass class _Sentences` (línea 210):

```python
def _best_display_name(display: Counter[str]) -> str:
    """Elige la variante más COMPLETA como nombre a mostrar, no la más
    repetida: dentro de un mismo artículo una sigla puede aparecer más veces
    que el nombre completo (p.ej. "PLD" 5 veces vs. "Partido de la
    Liberación Dominicana" 1 vez), pero el nombre completo es la forma
    canónica que espera quien lee el resultado — y la que puede coincidir
    con el nombre etiquetado a mano en el golden set (medido:
    tests/eval/golden_set.jsonl, odin-db-008/013/037/038 fallaban así antes
    de esta regla). Empate en palabras significativas -> gana la más usada.
    """
    return max(
        display,
        key=lambda name: (
            len([w for w in _norm_key(name).split() if w not in _NAME_PARTICLES]),
            display[name],
        ),
    )
```

Y reemplazar, dentro de `_entities` (línea 510):

```python
            display = g["display"].most_common(1)[0][0]  # variante más usada
```

por:

```python
            display = _best_display_name(g["display"])
```

- [x] **Step 4: Confirmar que pasan**

Run: `pytest tests/analysis/test_local_analyzer.py -v`
Expected: PASS — todos.

- [ ] **Step 5: Commit**

```bash
git add src/odin/analysis/local_analyzer.py tests/analysis/test_local_analyzer.py
git commit -m "fix: prefer the most complete entity name over the most frequent when merging aliases"
```

---

## Task 3: Resolver siglas dominicanas conocidas contra el catálogo estático

**Files:**

- Modify: `src/odin/analysis/local_analyzer.py:38-42` (import), `:112`
  (constante nueva), `:477-491` (loop de recolección de entidades)
- Modify: `src/odin/db/seed_aliases.py:128-137` (agregar `ITLA`)
- Test: `tests/analysis/test_local_analyzer.py`

**Interfaces:**

- Consumes: `SEED_ALIASES: list[tuple[str, str, str]]` de
  `odin.db.seed_aliases` (ya existe, formato `(sigla, nombre_canónico,
tipo)`; import directo de la lista, no de `db.aliases` — ese último exige
  sesión de BD, ver Global Constraints).
- Produces: `_SEED_ALIAS_MAP: dict[tuple[str, str], str]` — constante de
  módulo en `local_analyzer.py`, no consumida por otras tareas de este
  plan.

**Nota de alcance**: se agrega `ITLA` (confirmado ausente del catálogo,
causa el fallo medido en `odin-db-021`) porque su sigla es silábica ("Las"
aporta la L) y no la deriva el algoritmo de iniciales existente
(`_merge_aliases`/`_initials`). NO se agrega `PC` (Participación
Ciudadana, `odin-db-010`): son solo 2 caracteres y el filtro de longitud
existente (`local_analyzer.py:459`, `len(name) < 3`) la descarta antes de
llegar a esta resolución — arreglar eso exigiría tocar ese filtro de
longitud, sin evidencia de que valga la pena para un solo caso; queda fuera
de este plan.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar a `tests/analysis/test_local_analyzer.py`, después de la nueva
clase `TestGenericStateOrgFilter` (Tarea 1) y antes de
`TestEntitySentimentBoost`:

```python
class TestSeedAliasResolution:
    """Siglas del catálogo curado (db/seed_aliases.py) se resuelven al
    nombre canónico SIN necesitar que el artículo escriba el nombre
    completo — medido en el golden set: odin-db-008/012 solo dicen "PLD"
    en todo el cuerpo (ver tests/eval/golden_set.jsonl)."""

    @staticmethod
    def _org_names(nlp, text: str) -> set[str]:
        doc = nlp(text)
        sentences = _Sentences.from_doc(doc)
        probas_by_index = [None for _ in sentences.texts]
        entities = LocalAnalyzer()._entities(doc, probas_by_index, sentences)
        return {e.name for e in entities if e.type == "ORG"}

    def test_acronym_only_mention_resolves_to_canonical_name(self, nlp):
        orgs = self._org_names(nlp, "El vicepresidente del PLD, Iván Lorenzo, habló ayer.")
        assert "Partido de la Liberación Dominicana" in orgs
        assert "PLD" not in orgs

    def test_silabic_acronym_not_derivable_from_initials_resolves(self, nlp):
        orgs = self._org_names(
            nlp, "El ITLA anunció nuevas becas técnicas para el próximo semestre."
        )
        assert "Instituto Tecnológico de Las Américas" in orgs
        assert "ITLA" not in orgs
```

- [ ] **Step 2: Confirmar que fallan**

Run: `pytest tests/analysis/test_local_analyzer.py::TestSeedAliasResolution -v`
Expected: FAIL en ambos — hoy "PLD"/"ITLA" quedan tal cual, sin resolver
(y `ITLA` tampoco existe todavía en `SEED_ALIASES`).

- [ ] **Step 3: Agregar `ITLA` al catálogo**

En `src/odin/db/seed_aliases.py`, en la sección `# --- Universidades ---`
(líneas 127-137), agregar una línea después de `UFHEC`:

```python
    ("UFHEC",  "Universidad Federico Henríquez y Carvajal", "ORG"),
    ("ITLA",   "Instituto Tecnológico de Las Américas", "ORG"),
```

- [ ] **Step 4: Importar el catálogo y construir el mapa de resolución**

En `src/odin/analysis/local_analyzer.py`, agregar el import junto a los
demás `from odin...` (después de la línea 42):

```python
from odin.db.seed_aliases import SEED_ALIASES as _SEED_ALIASES
```

Y agregar la constante después de `_HEAD_CHAIN_DEPS` (línea 112), antes de
`def sentence_mentions_venue_word`:

```python
# Catálogo curado de siglas dominicanas (mismo que puebla la tabla
# `entity_aliases`, ver db/seed_aliases.py) — import directo de la lista en
# memoria, SIN tocar la BD: resuelve tanto siglas silábicas que
# `_merge_aliases`/`_initials` no puede derivar (MINERD, SENASA, INTRANT,
# ITLA...) como el caso en que el artículo NUNCA escribe el nombre completo
# (medido: odin-db-008/odin-db-012 solo dicen "PLD", nunca "Partido de la
# Liberación Dominicana" — ninguna fusión intra-artículo puede arreglar eso).
_SEED_ALIAS_MAP: dict[tuple[str, str], str] = {
    (_norm_key(alias), etype): canonical for alias, canonical, etype in _SEED_ALIASES
}
```

- [ ] **Step 5: Resolver en el loop de recolección de entidades**

En `_entities` (dentro de `src/odin/analysis/local_analyzer.py`), reemplazar:

```python
            if nkey in _KNOWN_ORGS:
                etype = "ORG"  # spaCy suele marcar estas marcas como PERSON
            elif not _is_proper_span(ent):
                continue
            elif etype == "PERSON" and (
                _is_named_after_place(ent) or _preceded_by_venue_noun(ent)
            ):
                continue
            key = (nkey, etype)
            g = groups.setdefault(
                key,
                {"display": Counter(), "count": 0, "mentions": defaultdict(list)},
            )
            g["display"][name] += 1
```

por:

```python
            if nkey in _KNOWN_ORGS:
                etype = "ORG"  # spaCy suele marcar estas marcas como PERSON
            elif not _is_proper_span(ent):
                continue
            elif etype == "PERSON" and (
                _is_named_after_place(ent) or _preceded_by_venue_noun(ent)
            ):
                continue
            key = (nkey, etype)
            canonical = _SEED_ALIAS_MAP.get(key)
            if canonical is not None:
                name = canonical
                key = (_norm_key(canonical), etype)
            g = groups.setdefault(
                key,
                {"display": Counter(), "count": 0, "mentions": defaultdict(list)},
            )
            g["display"][name] += 1
```

- [ ] **Step 6: Confirmar que pasan**

Run: `pytest tests/analysis/test_local_analyzer.py -v`
Expected: PASS — todos, incluidas las Tareas 1 y 2 ya implementadas.

- [ ] **Step 7: Commit**

```bash
git add src/odin/analysis/local_analyzer.py src/odin/db/seed_aliases.py tests/analysis/test_local_analyzer.py
git commit -m "feat: resolve known Dominican institutional acronyms via the static seed alias catalog"
```

---

## Task 4: Atenuar hacia NEU las frases con negación/desmentido explícito

**Files:**

- Modify: `src/odin/analysis/sentiment_lexicon.py` (nueva constante +
  funciones)
- Modify: `src/odin/analysis/local_analyzer.py:38-42` (import), `:412-414`
  (`_predict_batch`)
- Test: `tests/analysis/test_sentiment_lexicon.py`

**Interfaces:**

- Consumes: `_compile`, `strip_accents` (ya existen en
  `sentiment_lexicon.py`).
- Produces: `has_negation_cue(text: str) -> bool`,
  `dampen_negated(probas: dict[str, float], negated: bool, *, factor: float = 0.5) -> dict[str, float]`,
  `apply_negation_dampening(text: str, probas: dict[str, float]) -> dict[str, float]`
  — las tres públicas en `sentiment_lexicon.py`; `local_analyzer.py` solo
  consume `apply_negation_dampening`.

**Contexto de la lista de frases**: extraídas literalmente de los 2
artículos donde se midió el fallo (`odin-db-024`, `odin-db-025` —
`tests/eval/golden_set.jsonl`), no inventadas: _"No hay apagones, no
podemos hablar de apagones sino de sobrecarga"_, _"nosotros no damos
apagones de noche"_ (x2), _"negó que la interrupción eléctrica... sean
apagones"_, _"no se registran apagones"_. `odin-db-010` (el tercer artículo
NEU→NEG del golden set) se investigó y **no** entra en el alcance de esta
tarea: su causa es distinta (cita dos posturas enfrentadas sin que ninguna
domine — "detectar que dos citas se contradicen" no es lo que este fix
ataca).

- [ ] **Step 1: Escribir los tests que fallan**

Agregar a `tests/analysis/test_sentiment_lexicon.py`. Ampliar el import
(líneas 9-16):

```python
from odin.analysis.sentiment_lexicon import (
    PROMPT_GLOSSARY,
    apply_boost,
    apply_entity_relation_boost,
    apply_negation_dampening,
    dampen_negated,
    entity_relation_label,
    has_negation_cue,
    lexicon_label,
    lexicon_matches,
)
```

Nuevas clases al final del archivo (después de `TestPromptGlossary`):

```python
class TestHasNegationCue:
    def test_detects_common_denial_phrases(self):
        assert has_negation_cue(
            "No hay apagones, no podemos hablar de apagones sino de sobrecarga"
        )
        assert has_negation_cue("El funcionario negó las acusaciones en su contra")
        assert has_negation_cue("Nosotros no damos apagones de noche")

    def test_plain_statement_has_no_negation_cue(self):
        assert not has_negation_cue("Hubo un apagón anoche en el sector Los Ríos")


class TestDampenNegated:
    def test_pulls_probabilities_toward_neutral(self):
        probas = {"NEG": 0.7, "NEU": 0.2, "POS": 0.1}
        dampened = dampen_negated(probas, negated=True)
        assert dampened["NEG"] < probas["NEG"]
        assert abs(sum(dampened.values()) - 1.0) < 1e-9

    def test_noop_when_not_negated(self):
        probas = {"NEG": 0.7, "NEU": 0.2, "POS": 0.1}
        assert dampen_negated(probas, negated=False) == probas


class TestApplyNegationDampening:
    def test_dampens_when_text_has_negation_cue(self):
        probas = {"NEG": 0.7, "NEU": 0.2, "POS": 0.1}
        result = apply_negation_dampening("No hubo irregularidades en el proceso", probas)
        assert result["NEG"] < probas["NEG"]

    def test_noop_when_no_negation_cue(self):
        probas = {"NEG": 0.7, "NEU": 0.2, "POS": 0.1}
        assert apply_negation_dampening("Hubo un escándalo en el ministerio", probas) == probas
```

- [ ] **Step 2: Confirmar que fallan**

Run: `pytest tests/analysis/test_sentiment_lexicon.py -v`
Expected: FAIL — `ImportError: cannot import name 'has_negation_cue'`.

- [ ] **Step 3: Implementar en `sentiment_lexicon.py`**

Agregar, después de `_ENTITY_POS_PATTERNS` (línea 105) y antes del
comentario de `BOOST` (línea 107):

```python
# Frases de negación/desmentido explícito: pysentimiento (entrenado en
# tuits generales) no distingue "hay apagones" de "no hay apagones" —
# clasifica por el vocabulario que aparece sin pesar la negación que lo
# precede (medido: "No hay apagones, no podemos hablar de apagones sino de
# sobrecarga" puntúa NEG 0.63-0.96 pese a la negación explícita — ninguna
# palabra de ese ejemplo está en el léxico de arriba, así que el boost NO
# es la causa; es el modelo base). No intenta decidir hacia qué polaridad
# debería caer la frase negada (podría ser NEU o incluso lo contrario de lo
# que sugiere la palabra negada) — solo baja la confianza del modelo hacia
# NEU en vez de forzar una etiqueta a ciegas.
_NEGATION_CUES = [
    "no hay", "no es", "no fue", "no fueron", "no son",
    "no se registra", "no se registran", "no damos", "no dan",
    "no podemos hablar de", "nego", "negaron", "no sean", "no sea",
]
_NEGATION_RE = _compile(_NEGATION_CUES)
```

Y agregar, después de `apply_label_boost` (línea 214), antes de
`lexicon_matches`:

```python
def has_negation_cue(text: str) -> bool:
    """True si el texto trae una negación/desmentido explícito de
    `_NEGATION_CUES` — ver el comentario junto a la constante."""
    normalized = strip_accents(text).lower()
    return _NEGATION_RE.search(normalized) is not None


def dampen_negated(
    probas: dict[str, float], negated: bool, *, factor: float = 0.5
) -> dict[str, float]:
    """Si `negated`, acerca POS/NEG a NEU (con `factor=0.5`, reduce a la
    mitad la distancia a NEU) en vez de invertir la etiqueta a ciegas: no
    sabemos hacia qué polaridad debería caer la frase negada, solo que el
    modelo no debería estar tan seguro. No-op si `negated` es False."""
    if not negated:
        return probas
    neu = probas.get("NEU", 0.0)
    adjusted = {
        label: (neu + (prob - neu) * factor) if label != "NEU" else neu
        for label, prob in probas.items()
    }
    total = sum(adjusted.values())
    return {k: v / total for k, v in adjusted.items()}


def apply_negation_dampening(text: str, probas: dict[str, float]) -> dict[str, float]:
    """Combina `has_negation_cue` + `dampen_negated`: atenúa la frase hacia
    NEU si trae una negación/desmentido explícito. No-op en caso contrario."""
    return dampen_negated(probas, has_negation_cue(text))
```

- [ ] **Step 4: Confirmar que pasan**

Run: `pytest tests/analysis/test_sentiment_lexicon.py -v`
Expected: PASS — todos.

- [ ] **Step 5: Conectar en `_predict_batch`**

En `src/odin/analysis/local_analyzer.py`, agregar el import junto a los
demás de `sentiment_lexicon` (después de la línea 40):

```python
from odin.analysis.sentiment_lexicon import apply_negation_dampening as _apply_negation_dampening
```

Y en `_predict_batch`, reemplazar (línea 412-414):

```python
            for orig, row in zip(batch_orig, probs, strict=True):
                probas = {analyzer.id2label[i]: row[i].item() for i in analyzer.id2label}
                results[orig] = _apply_sentiment_boost(orig, probas)
```

por:

```python
            for orig, row in zip(batch_orig, probs, strict=True):
                probas = {analyzer.id2label[i]: row[i].item() for i in analyzer.id2label}
                probas = _apply_sentiment_boost(orig, probas)
                results[orig] = _apply_negation_dampening(orig, probas)
```

- [ ] **Step 6: Correr toda la suite**

Run: `pytest tests/analysis/ -v`
Expected: PASS — todos, incluidas las Tareas 1-3.

- [ ] **Step 7: Validar contra los 2 artículos que motivaron el fix**

Esto es el paso que de verdad importa — los tests unitarios prueban la
mecánica, no si el `factor=0.5` alcanza para mover el agregado del
artículo completo. Con el repo en la raíz:

```bash
PYTHONPATH=src python3 -c "
from odin.analysis.local_analyzer import LocalAnalyzer
import json

analyzer = LocalAnalyzer()
with open('tests/eval/golden_set.jsonl') as f:
    for line in f:
        row = json.loads(line)
        if row['id'] in ('odin-db-024', 'odin-db-025'):
            result = analyzer.analyze(row['title'], row['body'])
            print(row['id'], 'gold=NEU predicted=', result.overall_sentiment, result.sentiment_score)
"
```

Expected: `overall_sentiment` para ambos ya no es `NEG` (gold es `NEU` para
los dos). Si sigue dando `NEG`, subir `factor` en `dampen_negated`
(probar `0.7`) y repetir este chequeo antes de continuar — no avanzar a la
Tarea 5 con este caso sin resolver, es la evidencia que motivó la tarea.

- [ ] **Step 8: Commit**

```bash
git add src/odin/analysis/local_analyzer.py src/odin/analysis/sentiment_lexicon.py tests/analysis/test_sentiment_lexicon.py
git commit -m "feat: dampen sentiment toward neutral on explicit negation/denial cues"
```

---

## Task 5: Re-evaluar contra el golden set y fijar la nueva línea base

**Files:**

- Modify: `src/odin/analysis/local_analyzer.py:49` (`_LOCAL_ANALYZER_VERSION`)
- Create: `tests/eval/baselines/2026-08-14-local.json`
- Modify: `docs/PRECISION.md` §4, `docs/planning/conflicts.md`

**Interfaces:**

- Consumes: los 4 fixes de las Tareas 1-4, ya commiteados.
- Produces: nada que otra tarea consuma — última tarea del plan.

- [ ] **Step 1: Subir la versión del heurístico**

En `src/odin/analysis/local_analyzer.py`, cambiar (línea 49):

```python
_LOCAL_ANALYZER_VERSION = "6"
```

por:

```python
_LOCAL_ANALYZER_VERSION = "7"
```

- [ ] **Step 2: Correr toda la suite de tests**

Run: `pytest tests/ -q`
Expected: PASS — sin regresiones en ningún archivo, no solo en
`tests/analysis/`.

- [ ] **Step 3: Correr la evaluación completa contra el golden set**

```bash
python scripts/evaluate.py --analyzer local --out tests/eval/baselines/2026-08-14-local.json
```

Anotar la salida impresa completa (F1 de entidades overall/PERSON/ORG,
accuracy de `overall_sentiment`, accuracy de `sentiment_toward`) — son los
números reales que van al siguiente paso, no se inventan.

- [ ] **Step 4: Comparar contra la línea base anterior**

```bash
python3 -c "
import json
old = json.load(open('tests/eval/baselines/2026-08-13-local.json'))
new = json.load(open('tests/eval/baselines/2026-08-14-local.json'))
for key in ('overall', 'PERSON', 'ORG'):
    o = old['entities']['overall'] if key == 'overall' else old['entities']['by_type'].get(key, {})
    n = new['entities']['overall'] if key == 'overall' else new['entities']['by_type'].get(key, {})
    print(key, 'F1', o.get('f1'), '->', n.get('f1'))
print('overall_sentiment accuracy', old['overall_sentiment']['accuracy'], '->', new['overall_sentiment']['accuracy'])
print('sentiment_toward accuracy', old['entities']['overall']['sentiment_accuracy'], '->', new['entities']['overall']['sentiment_accuracy'])
"
```

Expected: F1 de ORG sube de forma clara (el objetivo directo de las Tareas
1-3); F1 de PERSON no baja (regresión); `overall_sentiment` accuracy sube o
se mantiene (el objetivo de la Tarea 4 es arreglar 2 de 17 casos, no todo
el clúster). Si ORG F1 no sube, o si PERSON F1 baja, **no continuar**:
volver a la tarea responsable y revisar antes de documentar nada.

- [ ] **Step 5: Registrar los resultados en `docs/PRECISION.md`**

Agregar una fila nueva a la tabla de `## 4. Historial de mediciones` (junto
a la fila `2026-08-13 | 42 | local | ...` ya existente) con los números
reales del Step 3 — no los de este plan, los que imprimió tu propia
corrida.

- [ ] **Step 6: Actualizar `docs/planning/conflicts.md`**

En la sección "Conflicto 4", agregar una nota fechada 2026-08-14 debajo del
"Estado" ya existente, resumiendo: los 4 fixes de este plan (filtro de
"Gobierno", nombre de display completo, resolución de siglas vía
`SEED_ALIASES`, atenuación de negación), los números antes/después medidos
en el Step 4, y — explícitamente — que el clúster más grande de errores de
`overall_sentiment` (dilución en artículos largos, 14 de los 17 casos
originales) sigue abierto y necesita más artículos en el golden set antes
de intentar un fix seguro (ver la sección "Fuera de alcance" de este plan).

- [ ] **Step 7: Commit**

```bash
git add src/odin/analysis/local_analyzer.py tests/eval/baselines/2026-08-14-local.json docs/PRECISION.md docs/planning/conflicts.md
git commit -m "docs: record measured LocalAnalyzer accuracy improvements against golden set"
```

---

## Verificación end-to-end

1. `pytest tests/ -q` — suite completa en verde.
2. `python scripts/evaluate.py --analyzer local --out /tmp/reporte_final.json`
   corre limpio y sin errores contra los 42 artículos.
3. F1 de ORG en el reporte final es mayor que 52.6% (la línea base de
   2026-08-13); F1 de PERSON no bajó de 94.9%.
4. `odin-db-024` y `odin-db-025` (re-chequeo manual del Task 4 Step 7) ya
   no predicen NEG cuando el gold es NEU.
5. `docs/PRECISION.md` §4 y `docs/planning/conflicts.md` muestran los
   números reales del 2026-08-14, no `_pendiente_` ni valores inventados.

---

## Apéndice: estimación de costo (por qué no se ejecutó todavía)

Estimado usando `superpowers:subagent-driven-development` (subagente
implementador + revisor por tarea, más revisión final de rama completa),
calibrado contra el costo real medido del plan anterior ejecutado en esta
misma sesión (`docs/superpowers/plans/` — expansión del golden set, 7
tareas, ~1.5M tokens totales incluyendo una tarea de etiquetado de datos
mucho más cara que cualquiera de las de aquí):

| Tarea                                                 | Estimado             |
| ----------------------------------------------------- | -------------------- |
| Tarea 1 (filtro "Gobierno")                           | ~70k tokens          |
| Tarea 2 (nombre de display)                           | ~70k tokens          |
| Tarea 3 (catálogo de siglas)                          | ~90k tokens          |
| Tarea 4 (amortiguador de negación)                    | ~100k tokens         |
| Tarea 5 (re-evaluación + docs)                        | ~60k tokens          |
| Revisión final de rama completa                       | ~100-120k tokens     |
| Contingencia (1 ronda de fix, probable en la Tarea 4) | ~50-80k tokens       |
| **Total estimado**                                    | **~550-650k tokens** |

**Relación costo/beneficio por tarea**: las Tareas 1 y 2 son las de mayor
beneficio por token — cambios de una función o una constante, riesgo casi
nulo, y la Tarea 1 sola ataca la causa individual más grande medida (≥18%
de los falsos negativos de ORG). Las Tareas 3-5 son válidas pero de menor
retorno relativo. Si se retoma este plan, ejecutar primero Tareas 1+2
aisladas (~140k tokens) es razonable sin comprometerse al resto.
