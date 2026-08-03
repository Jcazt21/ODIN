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

    # --- Análisis de encuadre (solo GeminiAnalyzer; NULL con LocalAnalyzer) ---
    framing: Mapped[str | None] = mapped_column(String(40))           # crisis_conflicto | logro_institucional | ...
    headline_intent: Mapped[str | None] = mapped_column(String(20))   # informativo | alarmista | sensacionalista
    lead_orientation: Mapped[str | None] = mapped_column(String(20))  # social | oficialista | tecnico
    dominant_actor: Mapped[str | None] = mapped_column(String(300))   # entidad con más peso en la nota
    source_quality: Mapped[str | None] = mapped_column(String(30))    # citas_directas | testimonios_anonimos | ...
    has_hard_data: Mapped[bool | None] = mapped_column(Boolean)       # ¿hay cifras verificables?
    blamed_actor: Mapped[str | None] = mapped_column(String(300))     # señalado como causante
    credited_actor: Mapped[str | None] = mapped_column(String(300))   # presentado como solución

    entities: Mapped[list[Entity]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
    )

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
