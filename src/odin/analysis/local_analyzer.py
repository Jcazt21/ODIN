"""Analizador local (gratis) en español.

Combina:
  - spaCy (es_core_news_lg) -> segmentación de frases + NER (PERSON / ORG)
  - pysentimiento -> sentimiento en español (POS / NEG / NEU)

Rendimiento: el sentimiento de cada frase ÚNICA se calcula UNA sola vez y se
reutiliza tanto para el sentimiento global como para el de cada entidad (antes
se recalculaba por frase y por entidad, con ~38% de llamadas redundantes).

Campos:
  - main_topic / topic_keywords: sustantivos y nombres propios frecuentes;
    el tema principal prefiere una frase nominal ("agua potable") si existe.
  - overall_sentiment: sentimiento agregado sobre TODAS las frases del artículo,
    reforzado por frase con el glosario político de
    `analysis/sentiment_lexicon.py` antes de agregar (ver `_predict_batch`).
    La agregación NO es un promedio: descuenta la tasa base de cada clase
    (ver `_aggregate_document`), porque promediar arrastra cualquier artículo
    hacia el prior del modelo (~50% NEU por frase).
  - entities + sentiment_toward: por cada figura/empresa se agregan las frases
    donde se le menciona. Los nombres se normalizan y se fusionan alias
    ("Policía" -> "Policía Nacional"). Esas frases también se refuerzan con
    el léxico RELACIONAL de `analysis/sentiment_lexicon.py` ("acusado de",
    "reconocido por"): a diferencia del léxico general (que se aplica a toda
    frase por igual), este solo aplica sobre las frases ya asociadas a esa
    entidad puntual, y dentro de la frase solo a la mención que RECIBE la
    acción — la más cercana antes del patrón (ver `_relational_boosts`), para
    no dejar mal parado también a quien acusa. Antes de atribuir una etiqueta
    POLAR se exige corroboración (ver `_aggregate_entity`).

Las dos agregaciones son distintas A PROPÓSITO y tiran en direcciones opuestas:
el artículo se agrega sobre decenas de frases (hay que des-diluir), la entidad
sobre una o dos (hay que ser conservador). Usar la misma función para ambas era
el defecto de raíz detrás del 59.5% de accuracy en ambas métricas.

NOTA: `sentiment_toward` es una aproximación por frase (aspect-based sentiment
sencillo) y tiene un TECHO ESTRUCTURAL medido: un modelo de frase no puede
decidir de QUIÉN es el sentimiento, así que toda entidad presente en una frase
polar hereda su polaridad. Sobre el golden set, ni la mejor regla de gating le
gana a responder siempre NEU. Para precisión real hace falta atribución por rol
sintáctico o el analizador con LLM (misma interfaz Analyzer); ver
analysis/gemini_analyzer.py y docs/PRECISION.md §4.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from odin.analysis.base import AnalysisResult, EntityResult, PlaceResult
from odin.analysis.sentiment_lexicon import apply_boost as _apply_sentiment_boost
from odin.analysis.sentiment_lexicon import apply_label_boost as _apply_label_boost
from odin.analysis.sentiment_lexicon import apply_negation_dampening as _apply_negation_dampening
from odin.analysis.sentiment_lexicon import entity_relation_hits as _entity_relation_hits
from odin.analysis.text_norm import norm_key as _norm_key
from odin.analysis.text_norm import strip_accents as _strip_accents
from odin.db.seed_aliases import SEED_ALIASES as _SEED_ALIASES

# Versión de la heurística de LocalAnalyzer (§2.1 de task.md): subirla cuando
# cambie una regla que afecta el resultado (_VENUE_WORDS, _is_named_after_place,
# _merge_aliases, umbrales de _extraction_confidence, el glosario de
# analysis/sentiment_lexicon.py...), para poder distinguir en la BD qué filas
# se analizaron con qué versión del código.
_LOCAL_ANALYZER_VERSION = "8"

_MAX_SENT_CHARS = 500        # límite por frase para el modelo de sentimiento
_MAX_SENTENCES = 400         # tope de seguridad para artículos patológicos
_MIN_PROB = 1e-9             # piso para no hacer log(0) en `_aggregate_document`
# Cabezas institucionales que spaCy casi siempre etiqueta LOC, no ORG, porque
# las trata como metonimia del país. Medido sobre el golden set: "Gobierno" sale
# LOC 25 veces contra 2 como ORG — y era el falso negativo INDIVIDUAL más grande
# de ORG (11 de 48). Quitarlo de `_GENERIC_STATE_ORGS` (2026-08-14) no alcanzó,
# porque ese filtro solo actúa sobre spans que spaCy ya marcó ORG. Aquí se
# promueve el span sin importar qué etiqueta le puso spaCy.
#
# Aplica a la cabeza exacta o seguida de complemento ("Gobierno de Venezuela",
# "Gobierno dominicano"), que es como la prensa nombra al actor político.
_INSTITUTION_HEADS = ("gobierno", "presidencia", "poder judicial", "ministerio publico")
# frases de mención que deben COINCIDIR en una etiqueta polar para atribuírsela
# a una entidad; con menos, `_aggregate_entity` responde NEU (ver su docstring)
_MIN_ENTITY_POLAR_SENTENCES = 2

# Tasa base de sentimiento por frase de pysentimiento sobre prensa dominicana.
# `_aggregate_document` la descuenta para quitar el sesgo de clase del modelo
# (ver su docstring). Se estima con `scripts/estimate_sentiment_prior.py` sobre
# un corpus SIN etiquetar e independiente del golden set — así los 42 artículos
# de tests/eval/golden_set.jsonl siguen siendo conjunto de prueba limpio.
#
# El fallback es el prior medido sobre el propio golden set (680 frases). Se usa
# solo si falta el archivo: sirve para que el analizador funcione en una
# instalación limpia, pero mezcla levemente train y test, así que la corrida de
# evaluación oficial debe hacerse con el archivo generado.
_SENTIMENT_PRIOR_PATH = Path(__file__).with_name("sentiment_prior.json")
_FALLBACK_SENTIMENT_PRIOR = {"NEG": 0.2826, "NEU": 0.4967, "POS": 0.2207}


def _load_sentiment_prior() -> dict[str, float]:
    try:
        raw = json.loads(_SENTIMENT_PRIOR_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return dict(_FALLBACK_SENTIMENT_PRIOR)
    prior = {str(k): float(v) for k, v in (raw.get("prior") or {}).items()}
    # un prior incompleto o con un cero haría explotar el log: preferimos el
    # fallback conocido antes que un archivo a medio escribir
    if set(prior) != {"POS", "NEG", "NEU"} or any(v <= 0 for v in prior.values()):
        return dict(_FALLBACK_SENTIMENT_PRIOR)
    return prior


_SENTIMENT_PRIOR = _load_sentiment_prior()
_STOP_ENTITY_TOKENS = {"foto", "video", "listín", "listin", "diario", "libre"}
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
# las 31 provincias de RD + el Distrito Nacional: spaCy las etiqueta como
# PERSON cuando aparecen solas y capitalizadas entre paréntesis tras un nombre
# propio ("Moisés Ayala Pérez, (Barahona)") — el patrón "Nombre, (Lugar)" no
# le da suficiente contexto para distinguir el gentilicio del topónimo. Se
# filtran solo cuando son la entidad COMPLETA (mismo criterio que
# _GENERIC_STATE_ORGS): "Santiago" a secas cae aquí, pero "Santiago Zorrilla
# Sena" no, porque el span entero no coincide con ningún nombre de la lista.
_DOMINICAN_PROVINCES = {
    "azua", "bahoruco", "barahona", "dajabon", "distrito nacional",
    "duarte", "el seibo", "elias pina", "espaillat", "hato mayor",
    "hermanas mirabal", "independencia", "la altagracia", "la romana",
    "la vega", "maria trinidad sanchez", "monsenor nouel", "monte cristi",
    "montecristi", "monte plata", "pedernales", "peravia", "puerto plata",
    "samana", "san cristobal", "san jose de ocoa", "san juan",
    "san pedro de macoris", "sanchez ramirez", "santiago",
    "santiago rodriguez", "santo domingo", "valverde",
}
# Sustantivos que encabezan un accidente geográfico o una vía: spaCy los mete
# DENTRO del span LOC ("río Haina", "avenida Duarte"), así que basta mirar la
# primera palabra. Es el mismo criterio que _VENUE_WORDS usa para descartar
# personas que dan nombre a un lugar, aplicado en la otra dirección: acá lo
# que se descarta es el lugar mismo, porque un río no es una localidad.
_GEO_FEATURE_HEADS = {
    "rio", "arroyo", "canada", "canal", "presa", "lago", "laguna", "bahia",
    "playa", "loma", "cerro", "pico", "sierra", "cordillera", "valle",
    "puente", "avenida", "calle", "carretera", "autopista", "malecon",
    "parque", "plaza", "aeropuerto", "puerto",
}
# Conjunciones que spaCy no corta: devuelve "Hato Nuevo y Quita Sueño" como un
# solo span LOC. Se parte cuando ambas mitades siguen pareciendo nombres
# propios (empiezan en mayúscula), no cuando el "y" es parte del nombre.
_PLACE_CONJUNCTIONS = (" y ", " e ")
# Palabras con las que la prensa antepone el TIPO de unidad al nombre
# ("la provincia San Juan", "el municipio de Bajos de Haina"). spaCy las mete
# dentro del span, y sin quitarlas el mismo lugar cuenta como dos candidatos y
# la forma larga no resuelve —el nodo del catálogo se llama "San Juan" a
# secas—. Ojo con "villa": es prefijo administrativo en otros países, pero acá
# es parte del nombre de varios municipios (Villa González, Villa Altagracia),
# así que NO va en esta lista.
# Conectores que pueden quedar entre la unidad administrativa y el nombre
# ("el municipio DE Pedro Brand", "la provincia DE La Vega").
_ADMIN_LINK_TOKENS = {"de", "del", "la", "el", "los", "las"}
_ADMIN_PREFIXES = (
    "provincia", "municipio", "region", "región", "distrito municipal",
    "distrito", "sector", "barrio", "paraje", "seccion", "sección",
)
# tipos de entidad de spaCy que nos interesan -> tipo canónico
_WANTED_ENT = {"PER": "PERSON", "PERSON": "PERSON", "ORG": "ORG"}
# partículas que no rompen un nombre propio ("Policía del Distrito Nacional")
_NAME_PARTICLES = {"de", "del", "la", "las", "los", "y", "e"}
# marcas/redes sociales que spaCy suele etiquetar como PERSON por error
_KNOWN_ORGS = {
    "instagram", "facebook", "twitter", "x", "tiktok", "youtube",
    "whatsapp", "telegram", "linkedin",
}
# sustantivos de lugar/institución: cuando un nombre de persona cuelga de uno
# de estos (de cerca, o como cabeza en el árbol de dependencias), casi siempre
# es un topónimo/edificio/vía que lleva ese nombre en su honor, no la persona
# actuando en la noticia ("Casa del Pueblo Johnny Ventura", "avenida Abraham
# Lincoln", "Sala de Conferencias Juan Bosch").
_VENUE_WORDS = {
    "calle", "avenida", "autopista", "carretera", "salon", "sala",
    "auditorio", "asamblea", "conferencia", "coliseo", "estadio",
    "polideportivo", "gimnasio", "palacio", "casa", "centro", "complejo",
    "plaza", "plazoleta", "parque", "malecon", "puente", "glorieta",
    "rotonda", "monumento", "iglesia", "parroquia", "catedral", "escuela",
    "liceo", "colegio", "universidad", "instituto", "biblioteca", "museo",
    "teatro", "hospital", "clinica", "hotel", "aeropuerto", "puerto",
    "mercado", "club", "estacion", "terminal", "edificio", "torre",
    "residencial", "urbanizacion", "sector", "barrio", "condominio",
    "circunscripcion", "demarcacion", "subalcaldia", "subsecretaria",
    "tribunal", "gabinete", "despacho", "consultorio", "villa",
    # no son lugares, pero funcionan igual sintácticamente ("el homenaje a
    # Juan Pablo Duarte", "en honor a..."): el nombre que sigue no actúa, solo
    # recibe el homenaje/da nombre a algo.
    "homenaje", "honor", "tributo", "reconocimiento", "memoria",
}
# relaciones de dependencia que conectan un nombre propio con la palabra que
# describe qué es (para subir por la cadena y encontrar la cabeza real).
_HEAD_CHAIN_DEPS = {"appos", "flat", "nmod", "conj"}

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


def sentence_mentions_venue_word(text: str) -> bool:
    """True si el texto contiene alguna palabra de `_VENUE_WORDS` (chequeo
    léxico simple, sin spaCy) — usado para decidir cuándo vale la pena
    preguntarle al árbitro de Gemini si una mención de PERSON es ambigua."""
    words = _strip_accents(text.lower()).split()
    return any(w.strip(".,;:()\"'") in _VENUE_WORDS for w in words)


def _preceded_by_venue_noun(ent, window: int = 10) -> bool:
    """Mira hacia atrás desde la entidad (la más cercana primero); se detiene
    al cruzar un verbo, que marca el límite de la cláusula/sintagma actual.

    Respaldo barato de `_is_named_after_place` por si el parser de
    dependencias se equivoca; no depende del árbol, solo del orden lineal.
    """
    sent = ent.sent
    start = max(ent.start - window, sent.start if sent is not None else 0)
    for tok in reversed(ent.doc[start : ent.start]):
        if tok.pos_ == "VERB":
            break
        if _strip_accents(tok.lemma_.lower()) in _VENUE_WORDS:
            return True
    return False


def _is_named_after_place(ent, max_hops: int = 4) -> bool:
    """Sube por la cadena de dependencias desde la entidad buscando una
    cabeza tipo "lugar" (salón, avenida, casa...). A diferencia de la ventana
    de tokens, esto no depende de la distancia ni se confunde si hay un verbo
    de otra cláusula de por medio (p.ej. "el salón X ... se realizó...").
    """
    tok = ent.root
    for _ in range(max_hops):
        head = tok.head
        if head is tok:
            break
        if head.pos_ in {"NOUN", "PROPN"} and _strip_accents(head.lemma_.lower()) in _VENUE_WORDS:
            return True
        if tok.dep_ not in _HEAD_CHAIN_DEPS:
            break
        tok = head
    return False


def _is_proper_span(ent) -> bool:
    """Un nombre real casi siempre tiene todos sus tokens como PROPN (spaCy).

    Filtra spans que mezclan un título con un subtítulo pegado sin puntuación
    (p.ej. "Leonel Cuestionamientos", donde "Cuestionamientos" es NOUN, no
    PROPN) — un error típico de segmentación, no un nombre real.

    También filtra spans TRUNCADOS que terminan en una partícula ("Secretaría
    del", "Consejo Nacional de la") — spaCy a veces corta el span de NER antes
    de completarlo (frecuente cuando la siguiente palabra del nombre real ya
    quedó etiquetada como el inicio de OTRA entidad, p.ej. "Secretaría del
    [Consejo]" donde "Consejo" se extrae aparte). Un nombre propio real nunca
    termina en una preposición/artículo suelto.
    """
    alpha_tokens = [tok for tok in ent if tok.is_alpha]
    if alpha_tokens and alpha_tokens[-1].text.lower() in _NAME_PARTICLES:
        return False
    for tok in ent:
        if not tok.is_alpha:
            continue
        if tok.lemma_.lower() in _NAME_PARTICLES or tok.text.lower() in _NAME_PARTICLES:
            continue
        if tok.pos_ != "PROPN":
            return False
    return True


def _extraction_confidence(display_name: str, etype: str, count: int) -> float:
    """Qué tan segura estuvo la extracción de que esta es una mención real,
    no ruido. Señales baratas, disponibles ya en este punto del pipeline:

    - una sola mención en todo el artículo pesa menos que varias
      (más chance de ser un acierto aislado del NER, no un patrón repetido).
    - un nombre PERSON de una sola palabra significativa ("Fernández") es
      intrínsecamente más ambiguo que uno completo, incluso después de
      intentar resolverlo (`_resolve_partial_persons` en canonicalize.py
      puede no encontrar un único candidato).

    No incluye la señal del árbitro de Gemini: ese paso corre después, en
    api.py, fuera de LocalAnalyzer.
    """
    score = 1.0
    if count == 1:
        score -= 0.15
    if etype == "PERSON":
        words = [w for w in _norm_key(display_name).split() if w not in _NAME_PARTICLES]
        if len(words) <= 1:
            score -= 0.1
    return round(max(score, 0.1), 2)


# Un apodo/alias insertado ENTRE guiones, paréntesis o comillas, en medio de
# un nombre — patrón típico del periodismo dominicano ("Eduardo -Yayo- Sanz
# Lovatón", "Danilo (el Rubio) Medina", 'Juan "Manguera" Pérez'). Un solo
# guión suelto ("Jean-Claude") no matchea: hace falta el PAR que encierra
# algo. La alternativa de guiones va anclada a límites de espacio/cadena
# (`(?<!\S)...(?!\S)`) para que el guión de cierre solo pueda ser el que abre
# el MISMO token "-apodo-", y no el guión de un apellido compuesto distinto
# más adelante en el nombre (p.ej. "Jean-Claude Pérez-Gómez": sin el ancla,
# el guión de "Jean-" se emparejaba con el de "-Gómez", tragándose "Claude
# Pérez" como si fuera un apodo insertado).
_NICKNAME_SPLICE_RE = re.compile(
    r'(?<!\S)-[^-]{1,40}-(?!\S)|\([^)]{1,40}\)|"[^"]{1,40}"|\'[^\']{1,40}\'|“[^”]{1,40}”|«[^»]{1,40}»'
)


def _has_nickname_splice(name: str) -> bool:
    """True si `name` tiene un segmento entre guiones/paréntesis/comillas con
    texto real ANTES y DESPUÉS dentro del mismo nombre — es decir, insertado
    en medio, no un nombre que simplemente EMPIEZA o TERMINA entre comillas.
    """
    for m in _NICKNAME_SPLICE_RE.finditer(name):
        if name[: m.start()].strip() and name[m.end() :].strip():
            return True
    return False


# Vocabulario de unidad administrativa ya normalizado (sin acentos), para no
# pagarlo en cada token que se mira hacia atrás.
_ADMIN_PREFIXES_NORM = {_strip_accents(w).lower() for w in _ADMIN_PREFIXES}


@lru_cache(maxsize=1)
def _seed_place_keys() -> frozenset[str]:
    """Nombres y alias del catálogo geográfico, normalizados.

    Se leen de la semilla versionada (`db/seeds/localities_rd.json`), NO de la
    tabla: este módulo no habla con la base —resolver contra el catálogo vivo
    es trabajo de `services/locality_service`—. Acá solo hace falta saber si un
    nombre PUEDE ser un lugar dominicano, y para eso la semilla basta; ya se
    hace lo mismo con `_SEED_ALIASES` y con `_DOMINICAN_PROVINCES`.

    Sirve para lo que el etiquetado de spaCy no resuelve: "Pedro Brand" sale
    como PERSON porque "Pedro" es nombre de pila, y sin esta lista un municipio
    entero quedaría invisible para la detección de lugar.
    """
    from odin.db.localities import load_seed

    keys: set[str] = set()

    def add(node: dict) -> None:
        keys.add(_norm_key(node["nombre"]))
        for alias in node.get("alias", []):
            keys.add(_norm_key(alias))

    seed = load_seed()
    add(seed["pais"])
    for macro in seed["macrorregiones"]:
        add(macro)
        for region in macro["regiones"]:
            add(region)
            for prov in region.get("provincias", []):
                add(prov)
                for muni in prov.get("municipios", []):
                    add(muni)
    return frozenset(keys)


def _preceded_by_admin_unit(ent) -> bool:
    """¿Al span lo antecede "municipio de", "provincia de", "sector"...?

    Es la señal que permite recuperar un lugar que spaCy etiquetó como PERSON
    —"Pedro Brand" lo es porque "Pedro" es nombre de pila— sin dar por lugar a
    cualquier nombre propio. A una persona nadie la presenta como "el
    municipio de": el cargo ("el alcalde Ramón Pascual Gómez") y la vía ("la
    autopista Duarte") usan otras palabras y no pasan este filtro.
    """
    doc = ent.doc
    i = ent.start - 1
    # Saltar los conectores; el límite evita cruzar media oración buscando.
    for _ in range(3):
        if i < 0:
            return False
        token = _strip_accents(doc[i].text).lower()
        if token in _ADMIN_PREFIXES_NORM:
            return True
        if token not in _ADMIN_LINK_TOKENS:
            return False
        i -= 1
    return False


def _strip_admin_prefix(name: str) -> str:
    """"provincia San Juan" -> "San Juan"; "Villa González" queda intacto.

    Solo recorta si queda algo detrás: "provincia" a secas no es un lugar con
    nombre, y devolver "" lo convertiría en un candidato vacío.
    """
    lowered = _strip_accents(name).lower()
    for prefix in _ADMIN_PREFIXES:
        head = _strip_accents(prefix).lower()
        if not lowered.startswith(head + " "):
            continue
        rest = name[len(head):].strip()
        # "municipio DE Bajos de Haina": el enlace tampoco es parte del nombre.
        for link in ("de ", "del "):
            if _strip_accents(rest).lower().startswith(link):
                rest = rest[len(link):].strip()
                break
        if rest:
            return rest
    return name


def _split_place_span(text: str) -> list[str]:
    """"Hato Nuevo y Quita Sueño" -> ["Hato Nuevo", "Quita Sueño"].

    Solo parte cuando las DOS mitades siguen empezando en mayúscula: así
    "Santa Cruz de El Seibo" o "Las Yayas de Viajama" quedan enteras, y el
    "y" que une dos topónimos sí corta.
    """
    clean = " ".join(text.split()).strip(" ,.;:()")
    for conj in _PLACE_CONJUNCTIONS:
        if conj not in clean:
            continue
        left, _, right = clean.partition(conj)
        left, right = left.strip(), right.strip()
        if left[:1].isupper() and right[:1].isupper():
            return _split_place_span(left) + _split_place_span(right)
    return [clean] if clean else []


def _place_role(in_title: bool, count: int) -> tuple[str, float]:
    """Papel y confianza de un lugar según dónde y cuánto aparece.

    Escala conservadora a propósito: equivocarse hacia MENCIONADO le cuesta al
    documentalista un clic para corregir; equivocarse hacia HECHO mete un dato
    falso en el mapa de cobertura, que es justo lo que el reporte mide.
    """
    if in_title and count >= 2:
        return "HECHO", 0.9
    if in_title:
        return "HECHO", 0.75
    if count >= 3:
        return "HECHO", 0.6
    return "MENCIONADO", 0.4


def _best_display_name(display: Counter[str]) -> str:
    """Elige la variante más COMPLETA como nombre a mostrar, no la más
    repetida: dentro de un mismo artículo una sigla puede aparecer más veces
    que el nombre completo (p.ej. "PLD" 5 veces vs. "Partido de la
    Liberación Dominicana" 1 vez), pero el nombre completo es la forma
    canónica que espera quien lee el resultado — y la que puede coincidir
    con el nombre etiquetado a mano en el golden set (medido:
    tests/eval/golden_set.jsonl, odin-db-008/013/037/038 fallaban así antes
    de esta regla). Empate en palabras significativas -> gana la más usada.

    EXCEPCIÓN: una variante con un apodo insertado en medio (ver
    `_has_nickname_splice`) no cuenta su longitud extra para esta regla,
    aunque tenga más palabras "significativas" en bruto — ese apodo no es
    parte del nombre canónico, y dejarlo ganar por longitud produce un
    display name que ya no matchea por substring contiguo al nombre del
    golden set (odin-db-040: "Eduardo -Yayo- Sanz Lovatón" NO debe ganarle a
    "Sanz Lovatón" solo porque "Yayo" infla el conteo de palabras).
    """

    def word_count(name: str) -> int:
        if _has_nickname_splice(name):
            return 0
        return len([w for w in _norm_key(name).split() if w not in _NAME_PARTICLES])

    return max(display, key=lambda name: (word_count(name), display[name]))


@dataclass
class _Sentences:
    """Las frases del documento ya recortadas, más lo necesario para ubicar
    una entidad DENTRO de ellas.

    Existe para que el sentimiento por frase y la búsqueda de patrones
    relacionales trabajen sobre exactamente el mismo texto: antes las
    probabilidades se calculaban sobre la frase recortada a `_MAX_SENT_CHARS`
    y el léxico relacional se buscaba sobre la frase completa, así que un
    patrón que cayera después del corte ajustaba un sentimiento calculado
    sobre un texto donde ese patrón no estaba.
    """

    texts: list[str]                 # frase recortada, sin espacios al borde
    doc_starts: list[int]            # offset en el doc del primer carácter de texts[i]
    index_by_start: dict[int, int]   # start_char de la frase de spaCy -> índice

    @classmethod
    def from_doc(cls, doc) -> _Sentences:
        texts: list[str] = []
        doc_starts: list[int] = []
        index_by_start: dict[int, int] = {}
        for i, sent in enumerate(list(doc.sents)[:_MAX_SENTENCES]):
            raw = sent.text
            lead = len(raw) - len(raw.lstrip())
            texts.append(raw.strip()[:_MAX_SENT_CHARS])
            doc_starts.append(sent.start_char + lead)
            index_by_start[sent.start_char] = i
        return cls(texts, doc_starts, index_by_start)

    def index_of(self, sent) -> int | None:
        """Índice de la frase, o None si quedó fuera del tope de frases."""
        return self.index_by_start.get(sent.start_char)

    def offset_of(self, index: int, ent) -> int:
        """Posición de la entidad dentro de `texts[index]`."""
        return ent.start_char - self.doc_starts[index]


def _is_institution_head(nkey: str) -> bool:
    """True si el nombre normalizado ES una cabeza institucional de
    `_INSTITUTION_HEADS` o empieza por ella ("Gobierno de Venezuela"). Ver el
    comentario junto a la constante para por qué hace falta."""
    return any(nkey == head or nkey.startswith(f"{head} ") for head in _INSTITUTION_HEADS)


def _mean_probas(probas_list: Sequence[dict | None]) -> tuple[dict[str, float], int]:
    """Media de probabilidad por etiqueta, ignorando las frases sin puntuar.
    Devuelve también cuántas frases entraron en la media."""
    totals: dict[str, float] = defaultdict(float)
    n = 0
    for probas in probas_list:
        if not probas:
            continue
        for label, prob in probas.items():
            totals[label] += prob
        n += 1
    if n == 0:
        return {}, 0
    return {label: total / n for label, total in totals.items()}, n


def _aggregate_document(probas_list: Sequence[dict | None]) -> tuple[str, float]:
    """Sentimiento del ARTÍCULO completo.

    Combina las frases como evidencia independiente (suma de log-probabilidades)
    descontando la tasa base de cada clase, en vez de promediar probabilidades
    a secas. La media plana converge al prior del modelo: pysentimiento está
    entrenado en tuits y deja ~50% de masa NEU por frase, así que cuantas más
    frases se promedien más NEU sale el artículo, diga lo que diga.

    Ese era el mecanismo real detrás del 59.5% de accuracy — NO la "dilución en
    artículos largos" que suponía el plan anterior: los artículos mal
    clasificados eran de hecho MÁS CORTOS que los acertados (457 vs. 525
    palabras de media). Medido contra tests/eval/golden_set.jsonl: el
    analizador emitía POS solo 3 veces en 42 artículos cuando el gold trae 12,
    y 14 de los 17 errores eran POS/NEG colapsando a NEU, con CERO confusiones
    POS<->NEG (el modelo acierta el signo; no se atrevía a salir de NEU).

    No hay ningún umbral que ajustar aquí: el prior se mide sobre un corpus
    aparte (ver `_SENTIMENT_PRIOR`), no se tunea contra el golden set.
    """
    evidence: dict[str, float] = defaultdict(float)
    raw: dict[str, float] = defaultdict(float)
    n = 0
    for probas in probas_list:
        if not probas:
            continue
        for label, prob in probas.items():
            evidence[label] += math.log(max(prob, _MIN_PROB)) - math.log(
                _SENTIMENT_PRIOR.get(label, 1 / 3)
            )
            raw[label] += prob
        n += 1
    if n == 0:
        return "NEU", 0.0
    label = max(evidence, key=lambda k: evidence[k])
    # el score sigue siendo la media de probabilidad CRUDA de la etiqueta
    # ganadora, para que la cifra que ya está guardada en BD siga significando
    # lo mismo que antes de este cambio
    return label, round(float(raw[label] / n), 4)


def _aggregate_entity(
    probas_list: Sequence[dict | None],
    relational_labels: Sequence[str | None] = (),
) -> tuple[str, float]:
    """Sentimiento HACIA una entidad, sobre las frases donde se la menciona.

    Deliberadamente NO aplica la corrección de prior de `_aggregate_document`:
    aquí la mediana es UNA sola frase de mención, así que no hay dilución que
    deshacer, y aplicarle la misma corrección lo EMPEORA (medido: 59.5% ->
    54.5%, porque el gold de `sentiment_toward` es 71.5% NEU).

    El fallo medido es de sobre-emisión, no de signo: cuando el modelo emite
    una etiqueta polar y el gold también es polar acierta el signo 24/25 = 96%,
    pero emite 73 etiquetas polares cuando solo 57 entidades lo son, y 48 de
    esas 73 caen sobre entidades cuyo gold es NEU. La causa es que la entidad
    hereda el sentimiento de TODA la frase: en "X criticó la corrupción del
    Gobierno" toda entidad presente recibe NEG, incluida la que solo está
    mencionada de paso — un modelo de frase no puede decidir de QUIÉN es el
    sentimiento.

    Por eso solo se emite POS/NEG cuando hay CORROBORACIÓN, que puede venir por
    dos vías:

    1. al menos `_MIN_ENTITY_POLAR_SENTENCES` frases de mención coinciden en
       esa etiqueta, o
    2. el léxico RELACIONAL apuntó explícitamente a esta entidad en esa frase
       ("acusado de", "reconocido por" — ver `_relational_boosts`). Eso ya es
       evidencia de que la entidad RECIBE la acción, no de que solo comparta
       frase con ella, así que una sola mención basta.

    `relational_labels` viene alineada con `probas_list` (una entrada por frase
    puntuada, `None` si el léxico relacional no dijo nada de esta entidad ahí).

    Accuracy 59.5% -> 71.0% y precisión de las etiquetas polares 32.9% -> 46.7%
    (los juicios polares falsos bajan de 48 a ~16), que es lo que importa
    cuando recaen sobre personas nombradas (docs/planning/task.md §8.2,
    exposición bajo Ley 172-13).

    Nota honesta: 71.0% NO le gana a responder siempre NEU (71.5% sobre este
    mismo conjunto). Se probaron 12 reglas de gating y ninguna lo supera — el
    techo es estructural, no de umbral. Esta regla se queda porque mejora la
    PRECISIÓN de lo que sí afirma (32.9% -> 46.7%) en vez de callar siempre.
    """
    mean, n = _mean_probas(probas_list)
    if n == 0:
        return "NEU", 0.0
    label = max(mean, key=lambda k: mean[k])
    if label != "NEU" and label not in relational_labels:
        agreeing = sum(
            1
            for probas in probas_list
            if probas and max(probas, key=lambda k: probas[k]) == label
        )
        if agreeing < _MIN_ENTITY_POLAR_SENTENCES:
            label = "NEU"
    return label, round(float(mean[label]), 4)


class LocalAnalyzer:
    name = "local"
    version = _LOCAL_ANALYZER_VERSION

    def __init__(self, spacy_model: str = "es_core_news_lg") -> None:
        self._spacy_model = spacy_model
        self._nlp = None
        self._sent = None

    # ---- carga perezosa de modelos ---------------------------------------------
    @property
    def nlp(self):
        if self._nlp is None:
            import spacy

            try:
                self._nlp = spacy.load(self._spacy_model)
            except OSError as exc:
                raise RuntimeError(
                    f"Falta el modelo de spaCy '{self._spacy_model}'. "
                    f"Instálalo con:  python -m spacy download {self._spacy_model}"
                ) from exc
            self._nlp.max_length = 2_000_000
        return self._nlp

    @property
    def model(self) -> str:
        # Nombre y versión reales SI el modelo ya está cargado (nlp.meta); si
        # no, el nombre del paquete configurado sin versión. Deliberadamente
        # NO fuerza la carga perezosa de spaCy solo para leer esta propiedad
        # (analyze() la lee para cada guardado): eso rompería cualquier
        # análisis ya hecho por otro medio (Gemini, un Analyzer de prueba) que
        # solo necesita registrar linaje, no re-cargar spaCy de paso.
        if self._nlp is not None:
            meta = self._nlp.meta
            return f"{meta.get('lang', '?')}_{meta.get('name', self._spacy_model)}-{meta.get('version', '?')}"
        return self._spacy_model

    @property
    def sent(self):
        if self._sent is None:
            from pysentimiento import create_analyzer

            self._sent = create_analyzer(task="sentiment", lang="es")
        return self._sent

    # ---- API pública ------------------------------------------------------------
    def analyze(self, title: str, body: str) -> AnalysisResult:
        text = f"{title}.\n\n{body}".strip()
        return self._analyze_doc(self.nlp(text))

    def analyze_batch(self, items: list[tuple[str, str]]) -> list[AnalysisResult]:
        """Analiza varios artículos en una sola pasada de spaCy (`nlp.pipe`).

        Evita el overhead por-llamada de invocar `nlp()` una vez por artículo;
        vale la pena cuando se procesa un lote (p.ej. todo un rastreo de una
        fuente) en vez de un artículo suelto."""
        texts = [f"{title}.\n\n{body}".strip() for title, body in items]
        return [self._analyze_doc(doc) for doc in self.nlp.pipe(texts)]

    def analyze_topics(self, title: str, body: str) -> tuple[str | None, list[str]]:
        """Solo `(main_topic, topic_keywords)`, sin entidades ni sentimiento.

        Para quien combina este analizador con otro motor y descarta el resto
        (`HybridAnalyzer`, que toma las entidades y el encuadre de Groq):
        corre spaCy con el NER apagado —el componente más caro de los que aquí
        no se usan— y NO toca pysentimiento, que era ~60% del tiempo de
        `analyze()` y terminaba en la basura.
        """
        text = f"{title}.\n\n{body}".strip()
        doc = self.nlp(text, disable=["ner"])
        keywords = self._keywords(doc)
        return self._main_topic(doc, keywords), keywords

    def extract_places(self, title: str, body: str) -> list[PlaceResult]:
        """Solo los lugares, sin entidades, tema ni sentimiento.

        Espeja `analyze_topics`, para el caso simétrico: quien combina este
        analizador con un motor LLM y solo quiere de acá lo que el LLM no da.
        Los lugares salen del NER de spaCy —reconocer "San Juan" como topónimo
        no exige entender el artículo—, así que se extraen igual sin importar
        quién lo haya leído. Sin este camino, la detección automática solo
        funcionaba con ODIN_ANALYZER=local.

        NO toca pysentimiento: era ~60% del tiempo de `analyze()` y acá el
        resultado se tiraría entero.
        """
        text = f"{title}.\n\n{body}".strip()
        return self._places(self.nlp(text))

    def _analyze_doc(self, doc) -> AnalysisResult:
        sentences = _Sentences.from_doc(doc)

        # --- sentimiento de cada frase, UNA sola vez y en batch ---
        probas_by_index = self._sentiment_per_sentence(sentences.texts)

        # --- sentimiento global ---
        overall_label, overall_score = _aggregate_document(probas_by_index)

        # --- tema principal + palabras clave ---
        keywords = self._keywords(doc)
        main_topic = self._main_topic(doc, keywords)

        # --- entidades + opinión hacia cada una ---
        entities = self._entities(doc, probas_by_index, sentences)

        # --- lugares candidatos (mismas entidades del doc, otra etiqueta) ---
        places = self._places(doc)

        return AnalysisResult(
            main_topic=main_topic,
            topic_keywords=keywords,
            overall_sentiment=overall_label,
            sentiment_score=overall_score,
            entities=entities,
            places=places,
        )

    # ---- helpers ----------------------------------------------------------------
    _SENT_BATCH_SIZE = 32  # mismo batch_size con el que pysentimiento carga el modelo

    def _sentiment_per_sentence(self, sent_texts: list[str]) -> list[dict | None]:
        """Probabilidades por frase, calculando cada frase ÚNICA una sola vez."""
        unique_texts = list(dict.fromkeys(t for t in sent_texts if t))
        probas_map = self._predict_batch(unique_texts)
        return [probas_map.get(t) for t in sent_texts]

    def _predict_batch(self, texts: list[str]) -> dict[str, dict]:
        """Igual que `self.sent.predict(texts)`, pero sin pasar por
        `Trainer.predict()` de pysentimiento (que arma un `datasets.Dataset` +
        DataLoader por llamada: ~500x más lento en CPU/MPS para lotes chicos,
        medido). Tampoco es una frase a la vez: eso también deja rendimiento en
        la mesa (sin aprovechar el paralelismo del batch). Aquí se tokeniza y
        corre el modelo directamente, en lotes de `_SENT_BATCH_SIZE`.

        Replica el mismo preprocesamiento y truncado que usa la librería —
        `preprocess_tweet` por frase + `truncation=True,
        max_length=tokenizer.model_max_length` + softmax sobre los logits,
        igual que `AnalyzerForSequenceClassification` — así que el softmax
        crudo es idéntico bit a bit al de la librería; el único paso propio
        de Odin es el ajuste de `analysis/sentiment_lexicon.apply_boost`
        aplicado después, sobre vocabulario político dominicano.
        """
        if not texts:
            return {}

        import torch
        from pysentimiento.preprocessing import preprocess_tweet

        analyzer = self.sent
        device = next(analyzer.model.parameters()).device
        preprocessed = [preprocess_tweet(t, **analyzer.preprocessing_args) for t in texts]

        results: dict[str, dict] = {}
        for start in range(0, len(texts), self._SENT_BATCH_SIZE):
            batch_orig = texts[start : start + self._SENT_BATCH_SIZE]
            batch_pre = preprocessed[start : start + self._SENT_BATCH_SIZE]
            enc = analyzer.tokenizer(
                batch_pre,
                padding=True,
                truncation=True,
                max_length=analyzer.tokenizer.model_max_length,
                return_tensors="pt",
            ).to(device)
            with torch.no_grad():
                logits = analyzer.model(**enc).logits
            probs = torch.softmax(logits, dim=1)
            for orig, row in zip(batch_orig, probs, strict=True):
                probas = {analyzer.id2label[i]: row[i].item() for i in analyzer.id2label}
                probas = _apply_sentiment_boost(orig, probas)
                results[orig] = _apply_negation_dampening(orig, probas)
        return results

    def _keywords(self, doc, top_k: int = 8) -> list[str]:
        counts: Counter[str] = Counter()
        for tok in doc:
            if tok.pos_ in {"NOUN", "PROPN"} and not tok.is_stop and len(tok.lemma_) > 3:
                lemma = tok.lemma_.lower()
                if lemma not in _STOP_ENTITY_TOKENS:
                    counts[lemma] += 1
        return [w for w, _ in counts.most_common(top_k)]

    def _places(self, doc) -> list[PlaceResult]:
        """Lugares candidatos a partir de las entidades LOC de spaCy.

        No resuelve contra el catálogo —eso necesita una sesión y vive en
        `services/locality_service.suggest_from_places`—. Acá solo se limpia
        el ruido de segmentación y se estima cuán probable es que el lugar
        sea DONDE OCURRIÓ el hecho y no uno más de los nombrados al pasar.

        Las tres reglas de limpieza salen de medir la salida real del modelo
        sobre el corpus (ver tests/analysis/test_local_places.py).
        """
        # El titular es todo lo anterior a la primera línea en blanco: así lo
        # arma `analyze()` (f"{title}.\n\n{body}").
        title_end = doc.text.find("\n\n")
        if title_end < 0:
            title_end = 0

        # Dos pasadas. La primera decide QUÉ nombres son lugares; la segunda
        # los cuenta. Hace falta separarlas porque la señal que rescata un
        # lugar mal etiquetado suele aparecer en UNA sola mención ("el
        # municipio de Pedro Brand") mientras el nombre se repite sin ella
        # ("Residentes de Pedro Brand"): contando solo la mención con señal, el
        # titular no pesaría y el lugar caería a MENCIONADO.
        candidatos: list[tuple] = []   # (nkey, texto, es_lugar, en_titular)
        confirmados: set[str] = set()

        for ent in doc.ents:
            if ent.label_ not in ("LOC", "PER", "MISC"):
                continue
            # Un salto de línea dentro del span significa que spaCy pegó el
            # final de un párrafo con el principio del siguiente
            # ("río Haina\nResidentes"). Mismo criterio que en `_entities`.
            if "\n" in ent.text:
                continue
            # Una vía o un edificio que lleva el nombre de un lugar no ES ese
            # lugar: "a la autopista Duarte" no es la provincia Duarte. Los dos
            # guardas ya existen para el mismo problema en `_entities`.
            #
            # Solo para spans que NO son LOC: cuando spaCy ya dijo "esto es un
            # lugar", la palabra de vía que lo antecede suele relacionarlo, no
            # bautizarlo — el titular del artículo 68 es "Puente ENTRE Hato
            # Nuevo y Quita Sueño", y ahí el puente no se llama como ellos, los
            # une. El guarda hace falta para los rescatados por nombre, que es
            # donde "autopista Duarte" entraría.
            # "el municipio de X" manda sobre los dos guardas: es adyacente e
            # inequívoco, mientras que ellos son heurísticas sobre una ventana
            # de 10 tokens o el árbol de dependencias, que cruzan de cláusula.
            # En el artículo 71 la mención decisiva ("...residencial Flor de
            # Loto, ubicado en el municipio de Pedro Brand") cuelga de
            # "residencial", y sin esta precedencia se perdía justo la que
            # confirma el lugar.
            es_unidad_admin = _preceded_by_admin_unit(ent)
            if (
                not es_unidad_admin
                and ent.label_ != "LOC"
                and (_preceded_by_venue_noun(ent) or _is_named_after_place(ent))
            ):
                continue
            for chunk in _split_place_span(ent.text):
                chunk = _strip_admin_prefix(chunk)
                nkey = _norm_key(chunk)
                if len(chunk) < 3 or nkey in _STOP_ENTITY_TOKENS:
                    continue
                if nkey.split(" ", 1)[0] in _GEO_FEATURE_HEADS:
                    continue
                # Un span que NO es LOC solo cuenta como lugar si algo lo
                # respalda: o el catálogo lo conoce, o el texto lo presenta
                # como unidad administrativa. Sin esto, cada nombre propio del
                # artículo entraría como candidato.
                es_lugar = (
                    ent.label_ == "LOC" or es_unidad_admin or nkey in _seed_place_keys()
                )
                candidatos.append((nkey, chunk, es_lugar, ent.start_char < title_end))
                if es_lugar:
                    confirmados.add(nkey)

        groups: dict[str, dict] = {}
        for nkey, chunk, _es_lugar, en_titular in candidatos:
            if nkey not in confirmados:
                continue
            g = groups.setdefault(
                nkey, {"display": Counter(), "count": 0, "in_title": False}
            )
            g["display"][chunk] += 1
            g["count"] += 1
            if en_titular:
                g["in_title"] = True

        places: list[PlaceResult] = []
        for g in groups.values():
            kind, confidence = _place_role(g["in_title"], g["count"])
            places.append(
                PlaceResult(
                    name=_best_display_name(g["display"]),
                    mentions_count=g["count"],
                    in_title=g["in_title"],
                    kind=kind,
                    confidence=confidence,
                )
            )
        places.sort(key=lambda p: (-p.confidence, -p.mentions_count, p.name))
        return places

    def _main_topic(self, doc, keywords: list[str]) -> str | None:
        """Tema principal: prefiere una frase nominal frecuente que incluya la
        palabra clave top (p.ej. 'agua potable'); si no, la palabra clave top."""
        if not keywords:
            return None
        top = keywords[0]
        chunk_counts: Counter[str] = Counter()
        for chunk in doc.noun_chunks:
            words = [t for t in chunk if not t.is_stop and t.is_alpha]
            if 2 <= len(words) <= 3:
                phrase = " ".join(t.lemma_.lower() for t in words)
                if top in phrase:
                    chunk_counts[phrase] += 1
        if chunk_counts:
            return chunk_counts.most_common(1)[0][0]
        return top

    def _entities(self, doc, probas_by_index, sentences: _Sentences) -> list[EntityResult]:
        # 1) recolectar menciones agrupadas por (clave normalizada, tipo)
        groups: dict[tuple[str, str], dict] = {}
        for ent in doc.ents:
            etype = _WANTED_ENT.get(ent.label_)
            if not etype:
                # Si no es un tipo deseado, verificar si es un acrónimo conocido
                # del catálogo — pueden estar etiquetados como MISC por spaCy
                name = " ".join(ent.text.split())
                nkey = _norm_key(name)
                # Checar ORG: todos los acrónimos silábicos del catálogo que
                # necesitaban esta resolución (MINERD, SENASA, INTRANT, ITLA)
                # son organizaciones. PERSON entries no necesitan este fallback.
                if (nkey, "ORG") in _SEED_ALIAS_MAP or _is_institution_head(nkey):
                    etype = "ORG"
                else:
                    continue
            # Un salto de línea dentro del span es la señal más confiable de
            # que trafilatura pegó un título con el subtítulo siguiente sin
            # puntuación ("Leonel\nCuestionamientos a operativos" -> spaCy
            # llega a etiquetar "Cuestionamientos" como PROPN por el contexto,
            # así que el filtro por POS solo no basta).
            if "\n" in ent.text:
                continue
            name = " ".join(ent.text.split())
            nkey = _norm_key(name)
            if len(name) < 3 or nkey in _STOP_ENTITY_TOKENS:
                continue
            # "República"/"Estado" solas (no como parte de un nombre propio
            # compuesto tipo "República Dominicana") no son una organización
            # real, son una forma genérica de referirse al país. ("Gobierno"
            # ya no se filtra aquí — ver el comentario junto a
            # _GENERIC_STATE_ORGS más arriba.)
            if etype == "ORG" and nkey in _GENERIC_STATE_ORGS:
                continue
            # "Santiago", "Elías Piña", "María Trinidad Sánchez"... spaCy las
            # marca PERSON cuando el span completo es el nombre de una
            # provincia dominicana (ver _DOMINICAN_PROVINCES).
            if etype == "PERSON" and nkey in _DOMINICAN_PROVINCES:
                continue
            # Cifras, montos y porcentajes ("RD$654", "39%") no son nombres:
            # spaCy a veces los etiqueta como PERSON/ORG porque son tokens no
            # alfabéticos que _is_proper_span deja pasar sin evaluar.
            if any(ch.isdigit() for ch in name):
                continue
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
            g["count"] += 1
            if ent.sent is not None:
                idx = sentences.index_of(ent.sent)
                if idx is not None:
                    # La posición, no solo el índice de la frase: es lo que
                    # permite saber si esta mención va antes o después de un
                    # patrón relacional (ver _relational_boosts).
                    g["mentions"][idx].append(sentences.offset_of(idx, ent))

        # 2) fusionar alias: nombre corto contenido en uno más largo (mismo tipo)
        groups = self._merge_aliases(groups)

        # 3) repartir el léxico relacional entre las entidades de cada frase
        boosts = self._relational_boosts(sentences, groups)

        # 4) construir resultados agregando el sentimiento ya calculado
        results: list[EntityResult] = []
        for key, g in groups.items():
            _nkey, etype = key
            display = _best_display_name(g["display"])
            sent_indices = sorted(g["mentions"])
            scored_indices = [i for i in sent_indices if probas_by_index[i] is not None]
            # qué dijo el léxico relacional sobre ESTA entidad en cada frase
            # puntuada: `_aggregate_entity` lo trata como corroboración
            # explícita (ver su docstring)
            relational = [boosts.get((key, i)) for i in scored_indices]
            probas = [
                _apply_label_boost(probas_by_index[i], boosts.get((key, i)))
                for i in scored_indices
            ]
            # Sin ninguna frase puntuada (p.ej. la entidad solo aparece más
            # allá de _MAX_SENTENCES) no hay opinión que reportar: None, no
            # un "NEU 0.0" indistinguible de un neutro de verdad.
            label, score = _aggregate_entity(probas, relational) if probas else (None, None)
            context = sentences.texts[sent_indices[0]] if sent_indices else None
            results.append(
                EntityResult(
                    name=display,
                    type=etype,
                    mentions_count=g["count"],
                    sentiment_toward=label,
                    sentiment_score=score,
                    context=context,
                    extraction_confidence=_extraction_confidence(display, etype, g["count"]),
                )
            )
        results.sort(key=lambda e: e.mentions_count, reverse=True)
        return results

    @staticmethod
    def _relational_boosts(
        sentences: _Sentences, groups: dict[tuple[str, str], dict]
    ) -> dict[tuple[tuple[str, str], int], str | None]:
        """Decide, frase por frase, QUÉ entidad recibe cada patrón del léxico
        relacional. Devuelve `(clave de entidad, índice de frase) -> etiqueta`.

        Antes el ajuste se aplicaba a la frase entera, así que en "Ramón Pérez
        fue acusado de corrupción por la Procuraduría" tanto el acusado como
        quien acusa se iban a NEG — justo la confusión que el léxico relacional
        existe para evitar.

        Regla: cada patrón se lo lleva la mención más cercana que lo PRECEDE.
        Todos los patrones del léxico son participios con preposición ("acusado
        de", "señalado por", "reconocido por"), donde el que recibe la acción va
        antes y el agente —si aparece— va después. Una entidad sin ninguna
        mención delante del patrón no recibe nada, y si dos patrones opuestos
        apuntan a la misma entidad en la misma frase se anulan (mismo criterio
        que `lexicon_label` ante señales contradictorias: no forzar nada).
        """
        mentions_by_sentence: dict[int, list[tuple[int, tuple[str, str]]]] = defaultdict(list)
        for key, g in groups.items():
            for idx, offsets in g["mentions"].items():
                mentions_by_sentence[idx].extend((offset, key) for offset in offsets)

        boosts: dict[tuple[tuple[str, str], int], str | None] = {}
        for idx, mentions in mentions_by_sentence.items():
            hits = _entity_relation_hits(sentences.texts[idx])
            if not hits:
                continue
            mentions.sort()
            for position, label in hits:
                preceding = [key for offset, key in mentions if offset < position]
                if not preceding:
                    continue
                target = (preceding[-1], idx)
                boosts[target] = label if boosts.get(target, label) == label else None
        return boosts

    @staticmethod
    def _initials(nkey: str) -> str:
        """Iniciales de las palabras significativas de un nombre normalizado."""
        words = [w for w in nkey.split() if w not in _NAME_PARTICLES]
        return "".join(w[0] for w in words if w)

    @classmethod
    def _merge_aliases(cls, groups: dict[tuple[str, str], dict]) -> dict[tuple[str, str], dict]:
        """Fusiona 'Policía' dentro de 'Policía Nacional' (subcadena por palabras)
        y 'FDD' dentro de 'Fundación Dominicana de Desarrollo' (siglas)."""
        keys = sorted(groups.keys(), key=lambda k: len(k[0]), reverse=True)  # largos 1º
        merged: dict[tuple[str, str], dict] = {}
        for key in keys:
            nkey, etype = key
            is_acronym_candidate = (
                " " not in nkey and 2 <= len(nkey) <= 6 and nkey.isalpha()
            )
            target = None
            for mkey in merged:
                if mkey[1] != etype:
                    continue
                # coincidencia por límites de palabra
                if f" {nkey} " in f" {mkey[0]} ":
                    target = mkey
                    break
                # coincidencia por siglas ("fdd" -> "fundación dominicana de desarrollo")
                if is_acronym_candidate and nkey == cls._initials(mkey[0]):
                    target = mkey
                    break
            if target is None:
                merged[key] = groups[key]
            else:
                dst = merged[target]
                src = groups[key]
                dst["display"].update(src["display"])
                dst["count"] += src["count"]
                for idx, offsets in src["mentions"].items():
                    dst["mentions"][idx].extend(offsets)
        return merged
