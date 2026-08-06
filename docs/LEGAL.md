# Legal y cumplimiento

> Este documento estructura las decisiones legales que Odin necesita antes de
> operar sobre datos de un cliente real. **No sustituye revisión por un
> abogado.** Las secciones marcadas 🔴 son decisiones pendientes que requieren
> criterio legal humano, no solo ingeniería — ver `task.md` §8.

## 1. Contenido de terceros (copyright de los medios)

Odin descarga y conserva el **cuerpo completo** de artículos de 9 medios
dominicanos (`articles.body`, sin límite de tamaño ni retención — ver
[DATA_DICTIONARY.md](DATA_DICTIONARY.md)). Ese texto tiene copyright del
medio que lo publicó.

| Medio | ToS revisados | Notas |
|---|---|---|
| Listín Diario | 🔴 pendiente | |
| Diario Libre | 🔴 pendiente | |
| Hoy | 🔴 pendiente | |
| El Nacional | 🔴 pendiente | |
| El Caribe | 🔴 pendiente | |
| Al Momento | 🔴 pendiente | |
| El Día | 🔴 pendiente | |
| N Digital | 🔴 pendiente | |
| Acento | 🔴 pendiente | scraping por regex sobre portada (sin sitemap/RSS fiable), ver [ADR-001](adr/0001-trafilatura-y-sitemaps-sobre-selectores.md) — revisar ToS con especial atención por ser el único medio sin mecanismo de descubrimiento "estándar" |

**Acción pendiente** (`task.md` §8.1): revisar los Términos de Servicio de
cada medio y llenar esta tabla con: ¿permite scraping automatizado?, ¿permite
conservar el cuerpo completo o solo un extracto?, ¿requiere atribución?
Mientras esta tabla esté en 🔴, tratar el guardado de `body` como riesgo legal
no mitigado, no como hecho consumado.

**Mitigaciones técnicas ya en el código** (no sustituyen la revisión de ToS,
la complementan):
- `robots.txt` se respeta por defecto (`ODIN_RESPECT_ROBOTS_TXT=true`,
  incluido `Crawl-delay` si es mayor que `REQUEST_DELAY`) —
  `scrapers/base.py`.
- Throttle real por dominio (`_DomainThrottle`), no solo backoff en error.
- `User-Agent` identificable: `OdinNewsBot/1.0 (+contacto: ...)` —
  configurable vía `USER_AGENT`; **cambiar el contacto de un email personal a
  uno de proyecto antes de producción** (pendiente de `task.md`, ítem #11).

**Decisión de retención pendiente** (🔴): ¿cuánto tiempo se conserva `body`?
Hoy: indefinidamente, sin política. Definir un TTL o criterio de archivado
antes de escalar volumen (ver también §4.6 de `task.md`).

## 2. Datos personales y perfilado (Ley 172-13 / GDPR)

Odin construye, de forma automatizada, un **perfil de opinión sobre personas
identificadas**: `entities.sentiment_toward` por `PERSON`, más
`articles.blamed_actor_id` / `credited_actor_id` / `dominant_actor_id`
(solo cuando el analizador es un LLM). Esto es tratamiento de datos
personales y, en la práctica, perfilado reputacional.

- **Jurisdicción primaria**: República Dominicana — aplica la **Ley 172-13**
  de Protección de Datos de Carácter Personal.
- **GDPR**: aplica si algún dato tratado o algún usuario del sistema está en
  la UE (poco probable dado el alcance actual, pero verificar antes de
  ofrecer el producto a un cliente con operación europea — art. 22 de GDPR
  en particular, sobre decisiones automatizadas con efecto legal o
  significativo).

### 2.1 Precisión y transparencia del juicio automatizado

El propio README documenta que `sentiment_toward` acierta ~60-70% (ver
[PRECISION.md](PRECISION.md) para la metodología real de esa cifra). Es
decir, **una fracción significativa de los juicios sobre una persona nombrada
es incorrecta**. Requisitos mínimos antes de mostrar esto a un cliente:

- [ ] Mostrar siempre `sentiment_score`/nivel de confianza junto al veredicto
      en la UI (no solo el resultado).
- [ ] Descargo explícito y visible de que es una inferencia automática, no
      un hecho verificado.
- [ ] No presentar los campos de encuadre solo-LLM (`framing`,
      `headline_intent`, `lead_orientation`, `source_quality`,
      `dominant_actor`/`blamed_actor`/`credited_actor`) como afirmaciones del
      medio — son inferencias de un tercer modelo sobre el texto del medio.

### 2.2 Rectificación y borrado

Estado actual del código (a diferencia del diagnóstico original de
`task.md` §8.2, esto **ya está resuelto**):

- `PUT /api/articles/{id}` y `PUT /api/entities/{id}` — rectificación de un
  artículo completo o de una mención puntual.
- `DELETE /api/articles/{id}` — borrado **permanente** del artículo (sin
  papelera ni archivado — irreversible).
- `DELETE /api/entities/{id}` — redacta el juicio sobre una persona en un
  artículo puntual sin borrar el artículo completo (más proporcionado cuando
  el reclamo es solo sobre la mención de esa persona).

**Pendiente** (🔴): procedimiento **documentado** de qué hacer cuando alguien
ejerce su derecho de rectificación/borrado bajo 172-13 — quién lo atiende,
en qué plazo, y si hay que notificar al cliente que consume el reporte.
Los endpoints técnicos existen; el proceso humano alrededor de ellos no está
escrito.

### 2.3 Base legal del tratamiento

🔴 Pendiente de definir con criterio legal: ¿bajo qué base legal de la Ley
172-13 se trata la opinión pública sobre figuras públicas? (interés
legítimo, información de interés público, etc.) Esto determina qué se le
puede decir a una persona que reclama sobre su perfil, y debe decidirse antes
de la primera entrega a cliente, no reactivamente ante un reclamo.

## 3. Superficie de exposición controlada por `url_guard.py`

`url_guard.py` (allowlist de dominios + bloqueo de IP privada + límites de
tamaño) es una defensa **técnica** contra SSRF/abuso, no una política legal,
pero define de facto "qué se le puede pedir al sistema que descargue" — el
alcance del negocio (9 medios dominicanos) está codificado ahí
(`ODIN_ALLOWED_DOMAINS`). Cualquier expansión de fuentes debe pasar primero
por §1 de este documento (revisión de ToS) antes de agregarse a la allowlist.

## 4. Checklist antes de entregar a un cliente

- [ ] Tabla de ToS por medio (§1) completa, no 🔴.
- [ ] Política de retención de `body` definida y, si corresponde,
      implementada (hoy no hay TTL).
- [ ] Confianza/descargo visible en la UI para juicios sobre personas (§2.1).
- [ ] Proceso humano de rectificación/borrado documentado (§2.2), no solo el
      endpoint técnico.
- [ ] Base legal de tratamiento definida con criterio legal (§2.3).
- [ ] `docs/PRECISION.md` con metodología y cifras reales, no estimaciones —
      un cliente puede tomar un porcentaje de precisión como compromiso
      contractual si no está claramente marcado como estimación con muestra
      pequeña.
- [ ] Revisión por alguien de legal antes de la primera entrega — este
      documento es un punto de partida para esa conversación, no un
      sustituto.
