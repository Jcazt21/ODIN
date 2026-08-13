"""Clasificador por palabras clave: ¿es este artículo de política dominicana?

Usado para acotar corridas del scraper (CLI `scripts/scrape_politics.py` y el
job de la API `scrape_jobs.py`) a solo noticias de política, con las que se
construye el golden set (task.md §2.4). Ningún scraper salvo Diario Libre
expone una sección "política" confiable, así que el filtro corre por palabras
clave sobre título + cuerpo del artículo ya extraído.
"""
from __future__ import annotations

import re
import threading
from collections import defaultdict
from collections.abc import Callable
from urllib.parse import urlparse

from odin.analysis.text_norm import strip_accents
from odin.scrapers.base import ScrapedArticle

# Vocabulario de política dominicana: instituciones, partidos, cargos, figuras
# y términos generales de cobertura electoral/legislativa. Coincidencia por
# palabra completa sobre texto sin acentos y en minúsculas (mismo criterio que
# analysis/text_norm.norm_key), para que "PRM" no matchee dentro de otra
# palabra y "políticas" no dependa de la tilde.
#
# Cada término debe ser inequívocamente político por sí solo. A propósito NO
# se incluyen palabras sueltas ambiguas ("ministro", "gobierno", "reforma",
# "protesta", "encuesta") aunque son frecuentes en noticias de política: sin
# calificar aparecen igual en economía, sucesos o deportes, y esto alimenta un
# golden set donde un falso positivo pesa más que uno que se escapa. Tampoco
# hay sistema de score/pesos: con vocabulario ya específico, un match simple
# alcanza sin sumar una capa de calibración.
_POLITICS_TERMS = [
    # instituciones y poderes del estado
    "presidencia de la republica", "poder ejecutivo", "palacio nacional",
    "senado", "senador", "senadora", "camara de diputados", "diputado", "diputada",
    "congreso nacional", "junta central electoral", "jce", "tribunal superior electoral",
    "tribunal constitucional", "suprema corte de justicia", "procuraduria general",
    "procurador general", "ministerio de la presidencia", "ayuntamiento", "sindico",
    "sindica", "regidor", "regidora", "gabinete ministerial", "cancilleria",
    "poder judicial", "camara de cuentas", "defensor del pueblo", "consejo de estado",
    "junta electoral", "liga municipal dominicana", "consultoria juridica",
    "contraloria general de la republica", "consejo nacional de la magistratura",
    "consejo economico y social",
    # gobierno municipal
    "alcaldia", "vicealcalde", "vicealcaldesa", "concejal", "distrito municipal",
    "fedomin",
    # partidos politicos
    "partido revolucionario moderno", "partido de la liberacion dominicana",
    "fuerza del pueblo", "partido revolucionario dominicano",
    "partido reformista social cristiano", "prm", "pld", "prd", "prsc", "fp",
    "gente de dominguez", "opcion democratica", "partido politico",
    "partido revolucionario independiente", "pri", "partido civico renovador", "pcr",
    "partido humanista dominicano", "phd", "partido verde dominicano",
    "partido fuerza nacional progresista", "fnp", "dominicanos por el cambio", "dxc",
    "alianza pais", "movimiento patria para todos", "mpt",
    # figuras (vigentes y recientes al momento de escribir esto)
    "luis abinader", "abinader", "danilo medina", "leonel fernandez", "abel martinez",
    "guillermo moreno", "hipolito mejia", "raquel pena", "carolina mejia",
    "victor orlando bisono",
    # terminos generales de cobertura politica/electoral
    "elecciones", "campana electoral", "candidato presidencial",
    "candidata presidencial", "candidatura", "reforma constitucional",
    "presupuesto nacional", "gobierno dominicano", "oposicion politica",
    "proyecto de ley", "decreto presidencial", "consulta popular",
    "boletin electoral", "encuesta electoral", "precandidato", "precandidata",
    "alcalde", "alcaldesa", "vicepresidenta de la republica",
    "vicepresidente de la republica",
    # proceso electoral
    "elecciones municipales", "elecciones congresuales", "elecciones generales",
    "elecciones presidenciales", "primarias electorales", "padron electoral",
    "colegio electoral", "recinto electoral", "mesa electoral", "escrutinio electoral",
    "fraude electoral", "delito electoral", "observador electoral",
    "segunda vuelta electoral", "registro electoral", "reglamento electoral",
    "delegado electoral", "delegada electoral",
    # proceso legislativo
    "asamblea nacional revisora", "reforma a la constitucion", "enmienda constitucional",
    "veto presidencial", "comision permanente", "ley electoral", "ley de partidos",
]


def _compile_politics_pattern() -> re.Pattern[str]:
    escaped = sorted({re.escape(strip_accents(t).lower()) for t in _POLITICS_TERMS}, key=len)
    return re.compile(r"\b(?:" + "|".join(escaped) + r")\b")


_POLITICS_RE = _compile_politics_pattern()

# Secciones de URL donde una mención política es casi siempre namedrop, no el
# tema de la nota — columnas de "sociales"/farándula que listan asistentes con
# cargo (boda con un senador invitado, feria inaugurada por la vicepresidenta).
# Vistas en las URLs reales de las 9 fuentes: listindiario usa "el-deporte" y
# "entretenimiento", el resto variantes de las mismas secciones.
_NON_POLITICS_SECTIONS = {
    "entretenimiento", "farandula", "espectaculos", "deportes", "el-deporte",
    "la-vida", "vivir", "moda", "gente", "loterias", "horoscopo", "turismo",
    "gastronomia",
}


def _url_section(url: str) -> str | None:
    path = urlparse(url).path.strip("/")
    return path.split("/", 1)[0].lower() if path else None


def is_dominican_politics(article: ScrapedArticle) -> bool:
    """Un solo término suelto en el cuerpo no basta: la prensa dominicana
    namedropea instituciones (ayuntamiento, vicepresidencia, poder judicial...)
    como fuente o asistente de eventos en notas de todo tipo — una feria
    inaugurada por la vicepresidenta, una boda con un funcionario invitado. Eso
    da falsos positivos con un solo `search()`.

    Primer filtro: la sección de la URL. Si es notoriamente no-política
    (farándula, deportes, moda...) se descarta sin mirar el texto — ahí el
    namedrop es casi garantizado y nunca es el tema.

    Si pasa eso, señal fuerte: el término aparece en el TÍTULO — un titular no
    menciona "PRM" o "Leonel Fernández" si la nota no es sobre eso. Sin eso, se
    exige corroboración: al menos 2 términos DISTINTOS en el cuerpo, no solo
    una repetición del mismo namedrop.
    """
    if _url_section(article.url) in _NON_POLITICS_SECTIONS:
        return False
    if _POLITICS_RE.search(strip_accents(article.title).lower()):
        return True
    body_matches = set(_POLITICS_RE.findall(strip_accents(article.body or "").lower()))
    return len(body_matches) >= 2


def make_filter(
    target: int, per_source_cap: int
) -> tuple[Callable[[ScrapedArticle], bool], dict[str, int]]:
    """Cierre con estado: decide qué artículos entran, respetando el tope
    global y el tope por fuente. `counts` se expone para el resumen final.

    `pipeline.run()` procesa las fuentes en paralelo (una por dominio, cada
    una con su propio thread) — este filtro es el único estado COMPARTIDO
    entre esos threads (el conteo global `target` no tiene sentido partido
    por fuente), así que el chequeo-e-incremento va bajo lock: sin esto, dos
    fuentes evaluando un artículo casi al mismo tiempo pueden pisarse el
    incremento y terminar aceptando más de `target` en total.
    """
    counts: dict[str, int] = defaultdict(int)
    total = 0
    lock = threading.Lock()

    def _filter(article: ScrapedArticle) -> bool:
        nonlocal total
        # Chequeo barato: no vale la pena tomar el lock si ya sabemos que no
        # califica sin siquiera mirar el contenido.
        if total >= target or counts[article.source] >= per_source_cap:
            return False
        # El regex sobre el body es lo más caro de esta función — se hace
        # SIN el lock, para no serializar el trabajo pesado de las 9 fuentes
        # entre sí. Solo el conteo (aritmética trivial) necesita ser atómico.
        if not is_dominican_politics(article):
            return False
        with lock:
            if total >= target or counts[article.source] >= per_source_cap:
                return False
            counts[article.source] += 1
            total += 1
            return True

    return _filter, counts
