"""Modelos de base de datos (SQLAlchemy 2.0).

Diseñados para ser portables entre PostgreSQL (desarrollo) y SQL Server (cliente):
se usan tipos genéricos del ORM, sin funciones específicas de un motor.

Estructura:
  Article          -> un artículo de periódico con su análisis global.
  Entity           -> una mención de una figura/empresa EN UN artículo concreto,
                       con la opinión hacia ella en ese artículo. Conserva el
                       nombre tal como se mostró en ese artículo (puede diferir
                       de CanonicalEntity.name si luego se corrigió el nombre
                       canónico).
  CanonicalEntity  -> la figura/empresa como dimensión: una fila por persona u
                       organización real, sin importar en cuántos artículos ni
                       con qué variante de nombre aparezca. Permite contar
                       artículos por persona real (no por string) y que una
                       corrección manual del nombre canónico se refleje para
                       todas las menciones ya vinculadas.
  EntityAlias      -> sigla ("MINERD") y su nombre canónico, editable desde el frontend.
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # --- Identificación / procedencia ---
    source: Mapped[str] = mapped_column(String(100), index=True)   # p.ej. "listin_diario"
    url: Mapped[str] = mapped_column(String(1000), unique=True)
    title: Mapped[str] = mapped_column(String(600))
    authors: Mapped[str | None] = mapped_column(String(500))        # autores separados por ", "
    section: Mapped[str | None] = mapped_column(String(200))        # sección / categoría
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # --- Contenido ---
    body: Mapped[str | None] = mapped_column(Text)

    # --- Análisis global ("de qué se habla" y si es bueno/malo/neutro) ---
    main_topic: Mapped[str | None] = mapped_column(String(200))       # tema principal, p.ej. "agua potable"
    topic_keywords: Mapped[str | None] = mapped_column(String(600))   # palabras clave separadas por ", "
    overall_sentiment: Mapped[str | None] = mapped_column(String(10)) # "POS" | "NEG" | "NEU"
    sentiment_score: Mapped[float | None] = mapped_column(Float)      # confianza 0..1

    # --- Linaje del análisis (§2.1 de task.md): quién lo produjo, con qué
    # modelo exacto y qué versión, para poder explicar un resultado meses
    # después y decidir backfill selectivo en vez de re-analizar a ciegas.
    # Nulos en filas guardadas antes de esta columna (no hay forma de
    # reconstruir el linaje retroactivamente).
    analyzer_name: Mapped[str | None] = mapped_column(String(40))      # "local" | "gemini" | "groq"
    analyzer_model: Mapped[str | None] = mapped_column(String(80))     # "es_es_core_news_lg-3.8.0" | "gemini-3.5-flash" | "openai/gpt-oss-120b" | "es_es_core_news_lg-3.8.0+openai/gpt-oss-120b"
    analyzer_version: Mapped[str | None] = mapped_column(String(64))   # versión de la heurística/prompt
    analysis_schema_version: Mapped[int | None] = mapped_column(Integer)  # versión de AnalysisResult
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # --- Análisis de encuadre (solo analizadores LLM: GeminiAnalyzer/GroqAnalyzer; NULL con LocalAnalyzer) ---
    framing: Mapped[str | None] = mapped_column(String(40))           # crisis_conflicto | logro_institucional | ...
    headline_intent: Mapped[str | None] = mapped_column(String(20))   # informativo | alarmista | sensacionalista
    lead_orientation: Mapped[str | None] = mapped_column(String(20))  # social | oficialista | tecnico
    source_quality: Mapped[str | None] = mapped_column(String(30))    # citas_directas | testimonios_anonimos | ...
    has_hard_data: Mapped[bool | None] = mapped_column(Boolean)       # ¿hay cifras verificables?

    # --- Capas de sentimiento (también solo LLM; NULL con LocalAnalyzer) ---
    # `overall_sentiment` dice cómo queda la nota; esto dice de QUIÉN es esa
    # carga: los hechos que se reportan, el discurso que se cita, o la voz del
    # propio medio. Se guardan aparte porque son la señal que permite separar
    # "el medio critica" de "el medio transmite una crítica ajena".
    sentiment_basis: Mapped[str | None] = mapped_column(String(20))   # hechos_reportados | discurso_citado | mixto
    facts_sentiment: Mapped[str | None] = mapped_column(String(10))   # POS | NEG | NEU (hechos reportados)
    quoted_sentiment: Mapped[str | None] = mapped_column(String(10))  # POS | NEG | NEU (discurso citado)
    media_stance: Mapped[str | None] = mapped_column(String(30))      # neutra_transmisiva | critica | favorable | editorializante
    media_stance_evidence: Mapped[str | None] = mapped_column(String(500))  # señal textual que sustenta media_stance
    overall_sentiment_reason: Mapped[str | None] = mapped_column(String(800))  # justificación de overall_sentiment
    # Señales acumulables separadas por ", " (mismo idioma que topic_keywords;
    # 0..N por artículo, a diferencia de headline_intent/source_quality que
    # eligen una sola categoría): alarmismo | sensacionalismo |
    # dato_no_verificable | posible_ironia
    content_flags: Mapped[str | None] = mapped_column(String(200))

    # --- Actores del encuadre, como identidad canónica (no string suelto) ---
    # Nula cuando el análisis no señala actor, o cuando el nombre no resolvió
    # a ninguna entidad canónica de las ya vinculadas a este artículo.
    dominant_actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("canonical_entities.id", ondelete="SET NULL"), index=True, nullable=True
    )
    blamed_actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("canonical_entities.id", ondelete="SET NULL"), index=True, nullable=True
    )
    credited_actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("canonical_entities.id", ondelete="SET NULL"), index=True, nullable=True
    )

    entities: Mapped[list[Entity]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
    )
    dominant_actor: Mapped[CanonicalEntity | None] = relationship(foreign_keys=[dominant_actor_id])
    blamed_actor: Mapped[CanonicalEntity | None] = relationship(foreign_keys=[blamed_actor_id])
    credited_actor: Mapped[CanonicalEntity | None] = relationship(foreign_keys=[credited_actor_id])

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Article {self.source}: {self.title[:40]!r}>"


class Entity(Base):
    """Figura pública o empresa mencionada, con la opinión que el artículo expresa hacia ella."""

    __tablename__ = "entities"
    __table_args__ = (
        UniqueConstraint("article_id", "name", "type", name="uq_entity_per_article"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), index=True
    )

    name: Mapped[str] = mapped_column(String(300), index=True)     # p.ej. "Luis Abinader"
    type: Mapped[str] = mapped_column(String(20))                  # "PERSON" | "ORG"
    mentions_count: Mapped[int] = mapped_column(Integer, default=1)

    # --- Opinión hacia la entidad (¿hablan bien o mal de ella?) ---
    sentiment_toward: Mapped[str | None] = mapped_column(String(10))  # "POS" | "NEG" | "NEU"
    sentiment_score: Mapped[float | None] = mapped_column(Float)      # confianza 0..1
    context: Mapped[str | None] = mapped_column(Text)                 # frase(s) de ejemplo

    # ¿Cuán segura estuvo la extracción de que esta mención es real? 1.0 =
    # certera (varias menciones, span limpio); más baja cuando el nombre es
    # parcial y de una sola mención, señal de que conviene revisión manual.
    extraction_confidence: Mapped[float] = mapped_column(Float, default=1.0)

    # Nula hasta que se vincula (todas las escrituras nuevas la fijan; las
    # filas guardadas antes de esta columna quedan sin vínculo).
    canonical_entity_id: Mapped[int | None] = mapped_column(
        ForeignKey("canonical_entities.id", ondelete="SET NULL"), index=True, nullable=True
    )

    article: Mapped[Article] = relationship(back_populates="entities")
    canonical_entity: Mapped[CanonicalEntity | None] = relationship(back_populates="mentions")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Entity {self.name} ({self.type}) {self.sentiment_toward}>"


class CanonicalEntity(Base):
    """Dimensión de personas/organizaciones: una fila por figura real.

    `canonicalize_entities()` ya unifica el nombre dentro de cada artículo y
    contra lo ya guardado (siglas, apellido único...); esta tabla persiste
    ESE nombre resultante como fila durable, para poder agrupar menciones por
    identidad real (no por string) y permitir una corrección manual (renombrar
    o fusionar dos filas) que se refleje en todos los artículos ya vinculados,
    no solo en análisis futuros.
    """

    __tablename__ = "canonical_entities"
    __table_args__ = (
        UniqueConstraint("name", "type", name="uq_canonical_entity_name_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(300), index=True)        # "Luis Abinader"
    type: Mapped[str] = mapped_column(String(20))                     # "PERSON" | "ORG"
    description: Mapped[str | None] = mapped_column(String(300))      # "Presidente de la RD"

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    mentions: Mapped[list[Entity]] = relationship(back_populates="canonical_entity")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<CanonicalEntity {self.name} ({self.type})>"


class AnalyzeJob(Base):
    """Trabajo asíncrono de `POST /api/analyze` (§3.1 de task.md).

    Antes ese endpoint hacía, dentro del ciclo request/response: fetch HTTP
    externo (hasta 60s solo de red con reintentos), extracción, inferencia
    NLP y opcionalmente una llamada a Gemini — todo síncrono, sin timeout de
    proxy que lo sobreviva y sin forma de cancelar. Ahora el endpoint solo
    valida la URL y encola esta fila; el trabajo pesado corre en
    `BackgroundTasks` y el cliente hace polling de `GET /api/jobs/{job_id}`.
    """

    __tablename__ = "analyze_jobs"
    __table_args__ = (
        # (url, created_at): sirve a las dos consultas que se hacen por URL —
        # reusar el análisis reciente de una nota ya analizada y detectar que
        # otro job para la misma URL ya está corriendo (ver
        # `start_analyze_job`), las dos con un filtro por fecha encima.
        Index("ix_analyze_jobs_url_created_at", "url", "created_at"),
        # (status, created_at): para el barrido de arranque, que busca jobs
        # colgados y jobs terminados que ya pasaron su TTL.
        Index("ix_analyze_jobs_status_created_at", "status", "created_at"),
    )

    # UUID como clave pública (no el id autoincremental): un job_id no debe
    # dejar adivinar cuántos análisis se han pedido en total.
    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|running|done|failed
    # Paso del pipeline dentro de status="running" (fetching|analyzing|
    # canonicalizing — ver ANALYZE_STAGES en services/analyze_service.py):
    # para que el polling del frontend muestre en qué parte del análisis va,
    # no solo que "está corriendo". NULL fuera de running.
    stage: Mapped[str | None] = mapped_column(String(20))
    url: Mapped[str] = mapped_column(String(2048))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Resultado serializado como JSON de texto (el shape de AnalyzeResult, la
    # vista previa sin guardar — no el de ArticleDetail, que es el artículo ya
    # persistido):
    # no amerita columnas propias por ser de solo un consumidor (el propio
    # endpoint que lo produjo) y de vida corta.
    result_json: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AnalyzeJob {self.id} {self.status}>"


class CrawlRun(Base):
    """Resumen de una corrida del pipeline (§7.1 de task.md).

    Antes este resumen se calculaba en `pipeline.py` y solo se imprimía por
    consola: se perdía en cuanto terminaba el proceso. Persistirlo permite
    ver el historial de corridas (¿cuántos artículos nuevos por fuente?
    ¿cuánto duró? ¿falló algo?) sin depender de logs efímeros.
    """

    __tablename__ = "crawl_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Mismo ID que el correlation_id de los logs de esta corrida (ver
    # observability.py), para poder cruzar la fila con sus líneas de log.
    correlation_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(
        String(20), default="running"
    )  # running | success | failed | cancelled

    # Fuentes pedidas en esta corrida ("diario_libre, listin_diario"); None = todas.
    sources: Mapped[str | None] = mapped_column(String(300))
    analyzer_name: Mapped[str | None] = mapped_column(String(40))

    articles_discovered: Mapped[int] = mapped_column(Integer, default=0)
    articles_saved: Mapped[int] = mapped_column(Integer, default=0)
    articles_failed: Mapped[int] = mapped_column(Integer, default=0)

    # Detalle por fuente como JSON de texto ({"diario_libre": 5, ...}); no
    # amerita una tabla propia por lo pequeño y de solo-lectura que es.
    stats_by_source: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)  # traceback si status == "failed"

    def __repr__(self) -> str:  # pragma: no cover
        return f"<CrawlRun {self.correlation_id} {self.status}>"


class ScrapeJob(Base):
    """Trabajo asíncrono de `POST /api/scrape-jobs`: arranca una corrida del
    scraper de política dominicana (`pipeline.run()` + `analysis.politics_filter`)
    desde el frontend y expone su avance para polling, igual que `AnalyzeJob`
    hace para `POST /api/analyze`.

    A diferencia de `AnalyzeJob` (un solo resultado), una corrida de scraping
    tiene 9 fuentes, cada una en dos etapas (discover -> analyze) —
    `progress_json` guarda el estado de cada (fuente, etapa) bajo la clave
    compuesta `"fuente:etapa"` como `{source, stage, status, detail,
    updated_at}`, sobreescrito por clave en cada actualización (mismo
    criterio que `CrawlRun.stats_by_source`: no amerita una tabla propia por
    ser de solo-lectura y sin necesidad de consultarse por fuente). El
    resumen final ya vive en la fila `CrawlRun` que esta corrida produce
    (`crawl_run_id`).
    """

    __tablename__ = "scrape_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # uuid4, igual que AnalyzeJob.id

    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending | running | done | failed | cancelled
    target: Mapped[int] = mapped_column(Integer)
    per_source_cap: Mapped[int] = mapped_column(Integer)
    # local | groq | hybrid — nunca "gemini": esa opción no existe en el
    # request de la API (Literal en el schema), es política de costo, no
    # solo una preferencia de UI. Ver CLAUDE.md.
    analyzer_name: Mapped[str] = mapped_column(String(40))

    # Mismo correlation_id pasado a pipeline.run(): permite ubicar la fila
    # crawl_runs de esta corrida y cruzar logs sin duplicar contadores aquí.
    correlation_id: Mapped[str | None] = mapped_column(String(32), index=True)
    crawl_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("crawl_runs.id", ondelete="SET NULL"), index=True
    )
    crawl_run: Mapped[CrawlRun | None] = relationship(foreign_keys=[crawl_run_id])

    progress_json: Mapped[str | None] = mapped_column(Text)

    # Pedido de cancelación desde otro request (POST .../cancel); pipeline.run()
    # lo consulta cooperativamente vía should_stop() entre fuentes/artículos —
    # no hay forma de matar el trabajo a la fuerza, solo de pedirle que pare.
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ScrapeJob {self.id} {self.status}>"


class EntityAlias(Base):
    """Sigla de una organización y el nombre completo al que equivale.

    Resuelve dos casos que la heurística de `LocalAnalyzer` no puede:
      * siglas silábicas (MINERD, INTRANT, SENASA), que no son las iniciales
        del nombre completo y por tanto no se pueden inferir;
      * unificar sigla y nombre completo aunque aparezcan en artículos
        distintos (la fusión automática solo ve un artículo a la vez).

    El catálogo se siembra desde `db/seed_aliases.py` y a partir de ahí se
    administra desde el frontend (CRUD).
    """

    __tablename__ = "entity_aliases"
    __table_args__ = (
        UniqueConstraint("alias_key", "type", name="uq_alias_per_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    alias: Mapped[str] = mapped_column(String(100))                 # "MINERD" (como se muestra)
    alias_key: Mapped[str] = mapped_column(String(100), index=True) # "minerd" (normalizado, para buscar)
    canonical_name: Mapped[str] = mapped_column(String(300))        # "Ministerio de Educación..."
    type: Mapped[str] = mapped_column(String(20), default="ORG")    # "PERSON" | "ORG"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # desactivar sin borrar

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<EntityAlias {self.alias} -> {self.canonical_name}>"
